from dataclasses import replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import select

from app.models.ocr_extraction import OcrExtraction
from app.services.document_highlights import build_document_highlights
from app.services.ocr_folio import FolioRegion, locate_folio_region
from app.services.ocr_preview import verify_ocr_preview_token
from app.services.pdf_ocr import render_pdf_pages
from app.services.textract_ocr import (
    TextractOcrResult,
    TextractOcrService,
    _combine_page_results,
    _merge_ocr_results,
    _parse_analyze_expense_response,
    _parse_detect_document_text_response,
)

FOLIO = "11111111-2222-3333-4444-AAAAAAAAAAAA"
OTHER = "88888888-2222-3333-4444-AAAAAAAAAAAA"


def _block(text=FOLIO, *, page=1, left=0.1, top=0.2, width=0.7, height=0.03, kind="LINE"):
    return {
        "BlockType": kind,
        "Text": text,
        "Page": page,
        "Geometry": {"BoundingBox": {"Left": left, "Top": top, "Width": width, "Height": height}},
    }


def _pdf(*, rotation=0, second_page=False, wrapped=False, crop=False):
    with PdfWriter() as writer, BytesIO() as output:
        if second_page:
            writer.add_blank_page(width=612, height=792)
        page = writer.add_blank_page(width=612, height=792)
        page.rotate(rotation)
        if crop:
            page.cropbox.lower_left = (20, 30)
            page.cropbox.upper_right = (590, 760)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        text = f"({FOLIO[:19]}) Tj 0 -16 Td ({FOLIO[19:]}) Tj" if wrapped else f"({FOLIO}) Tj"
        stream = DecodedStreamObject()
        stream.set_data(
            f"BT /F1 12 Tf 60 650 Td {text} 0 -80 Td (Fecha de emision: 07/08/2026) Tj 0 -50 Td (TOTAL: $100.00) Tj ET".encode(
                "ascii"
            )
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.write(output)
        return output.getvalue()


def _ocr_result(**kwargs):
    return TextractOcrResult(
        raw_text=f"COMERCIAL IAC\nCIA090819PW4\n{FOLIO}",
        extracted_total=Decimal("100.00"),
        extracted_date=date(2026, 8, 7),
        extracted_supplier=None,
        suggested_cfdi_uuid=FOLIO,
        confidence=Decimal(99),
        raw_response=None,
        **kwargs,
    )


def test_selected_folio_geometry_does_not_require_storing_raw_aws_response():
    block = _block()
    expense = _parse_analyze_expense_response(
        {"ExpenseDocuments": [{"Blocks": [block]}]}, store_raw_response=False
    )
    text = _parse_detect_document_text_response({"Blocks": [block]}, store_raw_response=False)
    for result in (expense, text):
        assert result.folio_region == FolioRegion(1, 0.1, 0.2, 0.7, 0.03)
        assert result.raw_response is None
        assert result.suggested_cfdi_uuid == FOLIO


def test_summary_geometry_and_rendered_page_override_are_used():
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "SummaryFields": [
                        {
                            "PageNumber": 1,
                            "Type": {"Text": "INVOICE_RECEIPT_ID"},
                            "ValueDetection": {"Text": FOLIO, "Geometry": _block()["Geometry"]},
                        }
                    ]
                }
            ]
        },
        store_raw_response=True,
        page_number=3,
    )
    assert result.folio_region.page == 3


@pytest.mark.parametrize("kind", ["LINE", "WORD"])
def test_wrapped_uuid_combines_only_nearby_blocks_on_same_page(kind):
    blocks = [
        _block(FOLIO[:19], width=0.4, kind=kind),
        _block(FOLIO[19:], top=0.24, width=0.3, kind=kind),
    ]
    assert locate_folio_region(blocks, FOLIO).height == pytest.approx(0.07)
    blocks[1]["Page"] = 2
    assert locate_folio_region(blocks, FOLIO) is None
    blocks[1]["Page"] = 1
    blocks[1]["Geometry"]["BoundingBox"]["Top"] = 0.8
    assert locate_folio_region(blocks, FOLIO) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"left": -0.1},
        {"top": float("nan")},
        {"width": float("inf")},
        {"width": 0},
        {"width": 0.95},
        {"height": 0.9},
        {"page": 0},
        {"page": 21},
        {"page": True},
    ],
)
def test_invalid_or_oversized_geometry_is_ignored(changes):
    assert locate_folio_region([_block(**changes)], FOLIO) is None


def test_missing_geometry_or_wrong_uuid_is_not_guessed():
    assert locate_folio_region([{"BlockType": "LINE", "Text": FOLIO}], FOLIO) is None
    assert locate_folio_region([_block(OTHER)], FOLIO) is None
    assert locate_folio_region([_block()], None) is None


def test_merge_and_page_combination_keep_geometry_for_selected_uuid_only():
    primary = _ocr_result()
    wrong = replace(
        primary, suggested_cfdi_uuid=OTHER, folio_region=FolioRegion(2, 0.1, 0.2, 0.7, 0.03)
    )
    assert _merge_ocr_results(primary, wrong).folio_region is None
    assert _combine_page_results([primary, wrong]).folio_region is None
    matching = replace(wrong, suggested_cfdi_uuid=FOLIO)
    assert _merge_ocr_results(primary, matching).folio_region.page == 2
    assert _combine_page_results([primary, matching]).folio_region.page == 2


def test_header_recovery_translates_region_back_to_original_page(monkeypatch, test_settings):
    service = TextractOcrService(test_settings)
    region = FolioRegion(3, 0.1, 0.25, 0.7, 0.05)
    monkeypatch.setattr(
        "app.services.textract_ocr.render_invoice_header", lambda *args, **kwargs: b"png"
    )
    monkeypatch.setattr(
        service, "_detect_text", lambda *args, **kwargs: _ocr_result(folio_region=region)
    )
    primary = replace(_ocr_result(), suggested_cfdi_uuid=None)
    result = service._recover_invoice_header_uuid(
        None, b"pdf", primary, filename="scan.pdf", is_pdf=False, page_number=3
    )
    assert result.folio_region.page == 3
    assert result.folio_region.top == pytest.approx(0.1)
    assert result.folio_region.height == pytest.approx(0.02)
    assert result.extracted_total == primary.extracted_total
    assert result.extracted_date == primary.extracted_date


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"second_page": True},
        {"wrapped": True},
        {"rotation": 90},
        {"rotation": 180},
        {"rotation": 270, "crop": True},
    ],
)
def test_document_highlights_cover_real_pixels_including_rotation(options):
    content = _pdf(**options)
    marks = build_document_highlights(content, _ocr_result(), include_folio=True)
    assert {item["field"] for item in marks} == {"date", "total", "folio"}
    pages = list(render_pdf_pages(content))
    for mark in marks:
        with Image.open(BytesIO(pages[mark["page"] - 1])) as image:
            box = (
                int(mark["left"] * image.width),
                int(mark["top"] * image.height),
                int((mark["left"] + mark["width"]) * image.width) + 1,
                int((mark["top"] + mark["height"]) * image.height) + 1,
            )
            with image.crop(box) as region:
                assert region.convert("L").getextrema()[0] < 80


def test_unknown_or_invalid_ocr_pages_are_omitted_for_scanned_documents():
    with PdfWriter() as writer, BytesIO() as output:
        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)
        writer.write(output)
        for page in (None, 3):
            result = _ocr_result(folio_region=FolioRegion(page, 0.1, 0.2, 0.7, 0.03))
            assert build_document_highlights(output.getvalue(), result, include_folio=True) == []


def test_api_preview_preserves_original_checksum_token_and_stored_ocr(
    client, monkeypatch, test_settings, session_factory
):
    test_settings.textract_enabled = True
    calls = []

    def extract(self, content, **kwargs):
        calls.append(content)
        return _ocr_result()

    monkeypatch.setattr(TextractOcrService, "extract_expense", extract)
    content = _pdf()
    response = client.post(
        "/api/v1/cfdi/ocr-preview", files={"file": ("factura.pdf", content, "application/pdf")}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert {item["field"] for item in data["document_highlights"]} == {"date", "total", "folio"}
    assert {item["page"] for item in data["document_highlights"]} == {1}
    assert "folio_preview" not in data
    assert calls == [content]
    assert data["checksum_sha256"] == sha256(content).hexdigest()
    payload = verify_ocr_preview_token(data["verification_token"], test_settings.auth_token_secret)
    assert payload["checksum_sha256"] == sha256(content).hexdigest()
    assert "folio_preview" not in payload
    assert "image_data_url" not in payload
    assert "document_highlights" not in payload
    with session_factory() as db:
        extraction = db.scalar(select(OcrExtraction))
        assert extraction.document_checksum_sha256 == sha256(content).hexdigest()
        assert extraction.raw_response is None
        assert extraction.raw_text == _ocr_result().raw_text


@pytest.mark.parametrize("case", ["render_failed", "no_folio", "vale", "recibo", "wrong_receiver"])
def test_optional_preview_never_changes_existing_validation_results(
    client, monkeypatch, test_settings, case
):
    test_settings.textract_enabled = True
    result = _ocr_result()
    if case == "no_folio":
        result = replace(result, suggested_cfdi_uuid=None)
    if case == "wrong_receiver":
        result = replace(result, raw_text="OTRA EMPRESA\nOTR010101AAA")
    monkeypatch.setattr(TextractOcrService, "extract_expense", lambda *args, **kwargs: result)
    render_calls = []

    def render(*args, **kwargs):
        render_calls.append(1)
        raise RuntimeError("highlight failure")

    monkeypatch.setattr("app.api.v1.endpoints.cfdi.build_document_highlights", render)
    response = client.post(
        "/api/v1/cfdi/ocr-preview",
        files={"file": ("factura.pdf", _pdf(), "application/pdf")},
        data={"document_type": case if case in ("vale", "recibo") else "factura"},
    )
    assert render_calls == ([] if case == "wrong_receiver" else [1])
    if case == "wrong_receiver":
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "OCR_RECEIVER_MISMATCH"
    else:
        assert response.status_code == 200, response.text
        assert response.json()["document_highlights"] == []
        assert response.json()["extracted_total"] == "100.00"


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"second_page": True},
        {"rotation": 90},
        {"rotation": 180},
        {"rotation": 270, "crop": True},
    ],
)
def test_native_pdf_highlights_all_fields_without_rasterizing(monkeypatch, options):
    monkeypatch.setattr(
        "app.services.pdf_ocr._render_page_bitmap",
        lambda *args: pytest.fail("No rasterization for field positions"),
    )
    content = _pdf(**options)
    marks = build_document_highlights(content, _ocr_result(), include_folio=True)
    assert {item["field"] for item in marks} == {"date", "total", "folio"}
    assert {item["page"] for item in marks} == {2 if options.get("second_page") else 1}
    assert all(
        0 <= item["left"] < 1 and 0 <= item["top"] < 1 and item["width"] > 0 and item["height"] > 0
        for item in marks
    )


def test_no_folio_can_still_highlight_date_and_total_and_vale_never_highlights_folio():
    for result in (_ocr_result(), replace(_ocr_result(), suggested_cfdi_uuid=None)):
        marks = build_document_highlights(_pdf(), result, include_folio=False)
        assert {item["field"] for item in marks} == {"date", "total"}
    empty = replace(
        _ocr_result(), extracted_total=None, extracted_date=None, suggested_cfdi_uuid=None
    )
    assert build_document_highlights(_pdf(), empty, include_folio=True) == []


def test_image_only_pdf_uses_aws_positions_with_raw_storage_disabled():
    with Image.new("RGB", (600, 800), "white") as image, BytesIO() as output:
        ImageDraw.Draw(image).text((60, 120), f"{FOLIO}\nFecha: 07/08/2026\nTOTAL $100.00", fill="black")
        image.save(output, format="PDF")
        content = output.getvalue()
    result = _parse_detect_document_text_response({"Blocks": [
        _block(), _block("Fecha: 07/08/2026", top=.3), _block("TOTAL $100.00", top=.4),
    ]}, store_raw_response=False)
    marks = build_document_highlights(content, result, include_folio=True)
    assert result.raw_response is None
    assert {item["field"] for item in marks} == {"date", "total", "folio"}
    assert {item["page"] for item in marks} == {1}


def test_aws_summary_geometry_is_kept_with_raw_response_off_and_selected_values_only():
    response = {
        "ExpenseDocuments": [
            {
                "Blocks": [_block()],
                "SummaryFields": [
                    {
                        "Type": {"Text": "TOTAL"},
                        "PageNumber": 1,
                        "ValueDetection": {
                            "Text": "$100.00",
                            "Geometry": _block(top=0.4)["Geometry"],
                        },
                    },
                    {
                        "Type": {"Text": "SUBTOTAL"},
                        "PageNumber": 1,
                        "ValueDetection": {
                            "Text": "$100.00",
                            "Geometry": _block(top=0.6)["Geometry"],
                        },
                    },
                    {
                        "Type": {"Text": "INVOICE_RECEIPT_DATE"},
                        "PageNumber": 1,
                        "ValueDetection": {
                            "Text": "07/08/2026",
                            "Geometry": _block(top=0.3)["Geometry"],
                        },
                    },
                ],
            }
        ]
    }
    result = _parse_analyze_expense_response(response, store_raw_response=False, page_number=2)
    assert result.raw_response is None and result.geometry_blocks
    marks = build_document_highlights(_pdf(second_page=True), result, include_folio=True)
    assert {item["page"] for item in marks} == {2}
    assert next(item for item in marks if item["field"] == "total")["top"] == 0.4
    assert next(item for item in marks if item["field"] == "date")["top"] == 0.3


def test_ambiguous_native_fields_are_not_guessed():
    from pypdf import PdfReader

    source = _pdf()
    reader = PdfReader(BytesIO(source))
    with PdfWriter() as writer, BytesIO() as output:
        writer.add_page(reader.pages[0])
        writer.add_page(reader.pages[0])
        writer.write(output)
        assert build_document_highlights(output.getvalue(), _ocr_result(), include_folio=True) == []


def test_geometry_merge_keeps_the_selected_value_and_drops_header_only_geometry(
    monkeypatch, test_settings
):
    first = _parse_detect_document_text_response(
        {"Blocks": [_block("TOTAL $100.00", top=0.5), _block("Fecha: 07/08/2026", top=0.3)]},
        store_raw_response=False,
        page_number=1,
    )
    second = _parse_detect_document_text_response(
        {"Blocks": [_block("TOTAL $200.00", top=0.6)]}, store_raw_response=False, page_number=2
    )
    merged = _merge_ocr_results(first, second)
    marks = build_document_highlights(_pdf(second_page=True), merged, include_folio=False)
    assert next(item for item in marks if item["field"] == "total")["page"] == 1
    combined = _combine_page_results([first, second])
    marks = build_document_highlights(_pdf(second_page=True), combined, include_folio=False)
    assert next(item for item in marks if item["field"] == "total")["page"] == 2
