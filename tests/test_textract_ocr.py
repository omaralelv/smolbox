from datetime import date
from decimal import Decimal
from hashlib import sha256
from io import BytesIO

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from PIL import Image, ImageDraw

from app.services.pdf_ocr import PdfOcrRenderError
from app.services.textract_ocr import (
    OCR_UNREADABLE_DOCUMENT_MESSAGE,
    TextractOcrError,
    TextractOcrResult,
    TextractOcrService,
    _parse_analyze_expense_response,
)


def _scanned_pdf(page_count: int = 1) -> bytes:
    pages = [Image.new("RGB", (360, 220), "white") for _ in range(page_count)]
    try:
        for page in pages:
            ImageDraw.Draw(page).text((20, 20), "RECIBO\nTOTAL $100.00", fill="black")
        output = BytesIO()
        pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:])
        return output.getvalue()
    finally:
        for page in pages:
            page.close()


def _expense_response(*lines: str) -> dict:
    return {
        "ExpenseDocuments": [
            {
                "Blocks": [{"BlockType": "LINE", "Text": line} for line in lines],
                "SummaryFields": [],
            }
        ]
    }


def _aws_error(code: str, operation: str = "AnalyzeExpense") -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "test failure"},
            "ResponseMetadata": {"RequestId": "test-request-id"},
        },
        operation,
    )


def test_analyze_expense_suggests_cfdi_uuid_from_ocr_text() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {
                            "BlockType": "LINE",
                            "Text": "Folio Fiscal 11111111-2222-3333-4444-aaaaaaaaaaaa",
                        }
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.suggested_cfdi_uuid == "11111111-2222-3333-4444-AAAAAAAAAAAA"


def test_analyze_expense_suggests_cfdi_uuid_from_compact_ocr_text() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {
                            "BlockType": "LINE",
                            "Text": "UUID 11111111222233334444aaaaaaaaaaaa",
                        }
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.suggested_cfdi_uuid == "11111111-2222-3333-4444-AAAAAAAAAAAA"


def test_analyze_expense_suggests_cfdi_uuid_from_spaced_ocr_text() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {
                            "BlockType": "LINE",
                            "Text": ("Folio Fiscal 11111111 2222 3333 4444 aaaaaaaaaaaa"),
                        }
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.suggested_cfdi_uuid == "11111111-2222-3333-4444-AAAAAAAAAAAA"


def test_analyze_expense_parses_invoice_date_with_time_from_summary() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [],
                    "SummaryFields": [
                        {
                            "Type": {"Text": "INVOICE_RECEIPT_DATE"},
                            "ValueDetection": {"Text": "2026-08-07T12:30:00"},
                        }
                    ],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.extracted_date == date(2026, 8, 7)


def test_analyze_expense_falls_back_to_ocr_text_for_spanish_invoice_date() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {"BlockType": "LINE", "Text": "Factura A-123"},
                        {
                            "BlockType": "LINE",
                            "Text": "Fecha de emisión: 07 de agosto de 2026",
                        },
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.extracted_date == date(2026, 8, 7)


def test_analyze_expense_prioritizes_invoice_date_over_stamp_date() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {
                            "BlockType": "LINE",
                            "Text": "Fecha de certificación: 09/08/2026",
                        },
                        {
                            "BlockType": "LINE",
                            "Text": "Fecha de emisión: 07/08/2026",
                        },
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.extracted_date == date(2026, 8, 7)


def test_analyze_expense_parses_invoice_date_when_label_is_on_previous_line() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {"BlockType": "LINE", "Text": "Fecha factura"},
                        {"BlockType": "LINE", "Text": "7 AGO 2026"},
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.extracted_date == date(2026, 8, 7)


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (("TOTAL $1,171.00",), Decimal("1171.00")),
        (("Total", "$ 100.00", "RFC CIA090819PW4"), Decimal("100.00")),
        (("La cantidad de $75.00",), Decimal("75.00")),
        (("Total impuestos trasladados $16.00", "Total $116.00"), Decimal("116.00")),
        (("Total $0.00",), Decimal("0.00")),
        (("Total", "Fecha: 12/09/2026"), None),
    ],
)
def test_analyze_expense_extracts_total_from_text_without_summary_fields(lines, expected) -> None:
    result = _parse_analyze_expense_response(_expense_response(*lines), store_raw_response=False)
    assert result.extracted_total == expected


@pytest.mark.parametrize("error_code", ["UnsupportedDocumentException", "BadDocumentException"])
def test_scanned_pdf_is_retried_as_png(monkeypatch, test_settings, caplog, error_code) -> None:
    content = _scanned_pdf()
    calls: list[bytes] = []

    class FakeClient:
        def analyze_expense(self, Document):
            calls.append(Document["Bytes"])
            if Document["Bytes"].startswith(b"%PDF-"):
                raise _aws_error(error_code)
            with Image.open(BytesIO(Document["Bytes"])) as page:
                assert page.format == "PNG"
                assert page.convert("L").getextrema()[0] < 255
            return _expense_response("Fecha: 07/08/2026", "Total $100.00")

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    result = service.extract_expense(content, content_type="application/pdf", filename="scan.pdf")

    assert result.extracted_total == Decimal("100.00")
    assert result.extracted_date == date(2026, 8, 7)
    assert len(calls) == 2
    assert calls[0] == content
    assert "operation=analyze_expense" in caplog.text
    assert f"error_code={error_code}" in caplog.text
    assert "request_id=test-request-id" in caplog.text


def test_rendered_pdf_reads_every_page_without_summing_repeated_invoice_totals(
    monkeypatch, test_settings
) -> None:
    test_settings.textract_enabled = True
    test_settings.textract_store_raw_response = True
    scanned_pages = 0

    class FakeClient:
        def analyze_expense(self, Document):
            nonlocal scanned_pages
            if Document["Bytes"].startswith(b"%PDF-"):
                raise _aws_error("UnsupportedDocumentException")
            scanned_pages += 1
            if scanned_pages == 1:
                return _expense_response("COMERCIAL IAC", "Fecha: 07/08/2026", "Total $100.00")
            return _expense_response(
                "CIA090819PW4",
                "Fecha: 07/08/2026",
                "Total $100.00",
                "Folio Fiscal 11111111-2222-3333-4444-AAAAAAAAAAAA",
            )

    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    result = service.extract_expense(
        _scanned_pdf(2), content_type="application/pdf", filename="two-pages.pdf"
    )

    assert scanned_pages == 2
    assert result.extracted_total == Decimal("100.00")
    assert "COMERCIAL IAC" in result.raw_text
    assert "CIA090819PW4" in result.raw_text
    assert result.suggested_cfdi_uuid == "11111111-2222-3333-4444-AAAAAAAAAAAA"
    assert len(result.raw_response["pages"]) == 2


def test_rendered_pdf_does_not_accept_partial_results_when_a_page_fails(
    monkeypatch, test_settings
) -> None:
    scanned_pages = 0

    class FakeClient:
        def analyze_expense(self, Document):
            nonlocal scanned_pages
            if Document["Bytes"].startswith(b"%PDF-"):
                raise _aws_error("UnsupportedDocumentException")
            scanned_pages += 1
            if scanned_pages == 2:
                raise _aws_error("AccessDeniedException")
            return _expense_response("Fecha: 07/08/2026", "Total $100.00")

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    with pytest.raises(TextractOcrError, match="AccessDeniedException"):
        service.extract_expense(
            _scanned_pdf(2), content_type="application/pdf", filename="two-pages.pdf"
        )
    assert scanned_pages == 2


@pytest.mark.parametrize(
    "error",
    [
        _aws_error("AccessDeniedException"),
        _aws_error("InvalidClientTokenId"),
        _aws_error("ThrottlingException"),
        EndpointConnectionError(endpoint_url="https://textract.us-east-1.amazonaws.com"),
    ],
)
def test_aws_access_or_connection_errors_do_not_trigger_pdf_conversion(
    monkeypatch, test_settings, caplog, error
) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            raise error

    def unexpected_render(content):
        raise AssertionError("Access/connection failures must not render the PDF")

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    monkeypatch.setattr("app.services.textract_ocr.render_pdf_pages", unexpected_render)
    with pytest.raises(TextractOcrError):
        service.extract_expense(_scanned_pdf(), content_type="application/pdf", filename="scan.pdf")
    assert "operation=analyze_expense" in caplog.text
    assert "region=us-east-1" in caplog.text
    assert "test failure" in caplog.text or "endpoint URL" in caplog.text


def test_client_initialization_failure_is_logged(monkeypatch, test_settings, caplog) -> None:
    def fail_client():
        raise RuntimeError("AWS credential provider failed")

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", fail_client)
    with pytest.raises(TextractOcrError):
        service.extract_expense(b"image", content_type="image/jpeg", filename="scan.jpg")
    assert "operation=create_client" in caplog.text
    assert "AWS credential provider failed" in caplog.text


def test_detect_document_text_completes_missing_fields_without_overwriting_total(
    monkeypatch, test_settings
) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            return _expense_response("COMERCIAL IAC", "Total $100.00")

        def detect_document_text(self, Document):
            return {
                "Blocks": [
                    {"BlockType": "LINE", "Text": text, "Confidence": 98}
                    for text in (
                        "CIA090819PW4",
                        "Fecha: 07/08/2026",
                        "Total $99.00",
                        "Folio Fiscal 11111111-2222-3333-4444-AAAAAAAAAAAA",
                    )
                ]
            }

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    result = service.extract_expense(b"image", content_type="image/jpeg", filename="scan.jpg")

    assert result.extracted_total == Decimal("100.00")
    assert result.extracted_date == date(2026, 8, 7)
    assert result.suggested_cfdi_uuid == "11111111-2222-3333-4444-AAAAAAAAAAAA"
    assert result.confidence == Decimal("98.00")
    assert result.raw_response is None
    assert "COMERCIAL IAC" in result.raw_text
    assert "CIA090819PW4" in result.raw_text


def test_detect_document_text_recovers_when_image_expense_analysis_cannot_read(
    monkeypatch, test_settings
) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            raise _aws_error("BadDocumentException")

        def detect_document_text(self, Document):
            return {"Blocks": [{"BlockType": "LINE", "Text": "Recibo de vigilancia"}]}

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    result = service.extract_expense(b"image", content_type="image/jpeg", filename="scan.jpg")
    assert result.raw_text == "Recibo de vigilancia"
    assert result.extracted_total is None
    assert result.extracted_date is None


def test_partial_read_remains_available_when_text_detection_permission_is_missing(
    monkeypatch, test_settings, caplog
) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            return _expense_response("COMERCIAL IAC", "CIA090819PW4")

        def detect_document_text(self, Document):
            raise _aws_error("AccessDeniedException", "DetectDocumentText")

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    result = service.extract_expense(b"image", content_type="image/jpeg", filename="scan.jpg")
    assert result.extracted_total is None
    assert result.extracted_date is None
    assert "COMERCIAL IAC" in result.raw_text
    assert "operation=detect_document_text" in caplog.text
    assert "error_code=AccessDeniedException" in caplog.text


def test_unreadable_document_does_not_become_a_successful_manual_read(
    monkeypatch, test_settings
) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            return _expense_response()

        def detect_document_text(self, Document):
            return {"Blocks": []}

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    with pytest.raises(TextractOcrError, match="no readable text"):
        service.extract_expense(b"image", content_type="image/jpeg", filename="scan.jpg")


def test_pdf_render_failure_is_logged(monkeypatch, test_settings, caplog) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            raise _aws_error("UnsupportedDocumentException")

    def fail_render(content):
        raise PdfOcrRenderError("PDF is password protected")

    test_settings.textract_enabled = True
    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeClient())
    monkeypatch.setattr("app.services.textract_ocr.render_pdf_pages", fail_render)
    with pytest.raises(TextractOcrError):
        service.extract_expense(
            b"%PDF-1.4\n%%EOF", content_type="application/pdf", filename="scan.pdf"
        )
    assert "operation=render_pdf" in caplog.text
    assert "PDF is password protected" in caplog.text


def test_extract_expense_falls_back_to_text_pdf_when_textract_rejects_document(
    monkeypatch,
    test_settings,
) -> None:
    test_settings.textract_enabled = True

    class FakeTextractClient:
        def analyze_expense(self, Document):
            raise RuntimeError("Request has unsupported document format")

    pdf_text = (
        "Folio fiscal:\n"
        "7F3EAC12-5857-4293-8CCA-416792CA7B33\n"
        "RFC receptor:\n"
        "CIA090819PW4\n"
        "Nombre receptor:\n"
        "COMERCIAL IAC\n"
        "Codigo postal, fecha y hora de emision:\n"
        "26010 2026-08-03 22:00:07\n"
        "Subtotal\n"
        "$ 1,085.49\n"
        "IVA\n"
        "$ 85.51\n"
        "Total\n"
        "$ 1,171.00"
    )

    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: FakeTextractClient())
    monkeypatch.setattr("app.services.textract_ocr._pdf_text_from_bytes", lambda content: pdf_text)

    result = service.extract_expense(
        b"%PDF-1.4\ncontent\n%%EOF",
        content_type="application/pdf",
        filename="factura.pdf",
    )

    assert result is not None
    assert result.suggested_cfdi_uuid == "7F3EAC12-5857-4293-8CCA-416792CA7B33"
    assert result.extracted_date == date(2026, 8, 3)
    assert result.extracted_total == Decimal("1171.00")


def test_extract_expense_uses_text_pdf_before_textract_when_data_is_complete(
    monkeypatch,
    test_settings,
) -> None:
    test_settings.textract_enabled = True

    class UnexpectedTextractClient:
        def analyze_expense(self, Document):
            raise AssertionError("Textract should not run when text PDF data is complete")

    pdf_text = (
        "Folio fiscal:\n"
        "7F3EAC12-5857-4293-8CCA-416792CA7B33\n"
        "RFC receptor:\n"
        "CIA090819PW4\n"
        "Nombre receptor:\n"
        "COMERCIAL IAC\n"
        "Codigo postal, fecha y hora de emision:\n"
        "26010 2026-08-03 22:00:07\n"
        "Total\n"
        "$ 1,171.00"
    )

    service = TextractOcrService(test_settings)
    monkeypatch.setattr(service, "_client", lambda: UnexpectedTextractClient())
    monkeypatch.setattr("app.services.textract_ocr._pdf_text_from_bytes", lambda content: pdf_text)

    result = service.extract_expense(
        b"%PDF-1.4\ncontent\n%%EOF",
        content_type="application/pdf",
        filename="factura.pdf",
    )

    assert result is not None
    assert result.suggested_cfdi_uuid == "7F3EAC12-5857-4293-8CCA-416792CA7B33"
    assert result.extracted_date == date(2026, 8, 3)
    assert result.extracted_total == Decimal("1171.00")


def test_invoice_ocr_preview_returns_verified_result(client, monkeypatch, test_settings) -> None:
    test_settings.textract_enabled = True

    def fake_extract_expense(self, content, *, content_type, filename):
        return TextractOcrResult(
            raw_text=(
                "Razón Social: COMERCIAL IAC\n"
                "RFC: CIA090819PW4\n"
                "Folio Fiscal 11111111-2222-3333-4444-aaaaaaaaaaaa"
            ),
            extracted_total=Decimal("100.00"),
            extracted_date=date(2026, 8, 7),
            extracted_supplier="Proveedor Demo",
            suggested_cfdi_uuid="11111111-2222-3333-4444-AAAAAAAAAAAA",
            confidence=Decimal("98.50"),
            raw_response=None,
        )

    monkeypatch.setattr(TextractOcrService, "extract_expense", fake_extract_expense)

    response = client.post(
        "/api/v1/cfdi/ocr-preview",
        files={"file": ("factura.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["suggested_cfdi_uuid"] == "11111111-2222-3333-4444-AAAAAAAAAAAA"
    assert body["extracted_total"] == "100.00"
    assert body["extracted_date"] == "2026-08-07"
    assert body["verification_token"].startswith("v1.")


def test_invoice_ocr_preview_rejects_wrong_receiver(client, monkeypatch, test_settings) -> None:
    test_settings.textract_enabled = True

    def fake_extract_expense(self, content, *, content_type, filename):
        return TextractOcrResult(
            raw_text=(
                "Razón Social: OTRA EMPRESA\n"
                "RFC: OTR010101AAA\n"
                "Folio Fiscal 11111111-2222-3333-4444-aaaaaaaaaaaa"
            ),
            extracted_total=Decimal("100.00"),
            extracted_date=date(2026, 8, 7),
            extracted_supplier="Proveedor Demo",
            suggested_cfdi_uuid="11111111-2222-3333-4444-AAAAAAAAAAAA",
            confidence=Decimal("98.50"),
            raw_response=None,
        )

    monkeypatch.setattr(TextractOcrService, "extract_expense", fake_extract_expense)

    response = client.post(
        "/api/v1/cfdi/ocr-preview",
        files={"file": ("factura.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "OCR_RECEIVER_MISMATCH"
    assert detail["missing_fields"] == ["razon_social", "rfc"]
    assert "COMERCIAL IAC" in detail["message"]
    assert "CIA090819PW4" in detail["message"]


def test_non_invoice_ocr_preview_does_not_require_invoice_receiver(
    client,
    monkeypatch,
    test_settings,
) -> None:
    test_settings.textract_enabled = True

    def fake_extract_expense(self, content, *, content_type, filename):
        return TextractOcrResult(
            raw_text="Vale interno con total 100.00",
            extracted_total=Decimal("100.00"),
            extracted_date=date(2026, 8, 7),
            extracted_supplier="Proveedor Demo",
            suggested_cfdi_uuid=None,
            confidence=Decimal("98.50"),
            raw_response=None,
        )

    monkeypatch.setattr(TextractOcrService, "extract_expense", fake_extract_expense)

    response = client.post(
        "/api/v1/cfdi/ocr-preview",
        data={"document_type": "vale"},
        files={"file": ("vale.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["extracted_total"] == "100.00"


def test_preview_and_upload_preserve_original_pdf_after_ocr_recovery(
    client, base_records, monkeypatch, test_settings
) -> None:
    content = _scanned_pdf()
    test_settings.textract_enabled = True
    test_settings.max_upload_bytes = 10 * 1024 * 1024
    calls = 0

    class FakeClient:
        def analyze_expense(self, Document):
            nonlocal calls
            calls += 1
            if Document["Bytes"].startswith(b"%PDF-"):
                raise _aws_error("UnsupportedDocumentException")
            return _expense_response(
                "COMERCIAL IAC", "CIA090819PW4", "Fecha: 07/08/2026", "Total $100.00"
            )

    monkeypatch.setattr(TextractOcrService, "_client", lambda self: FakeClient())
    preview = client.post(
        "/api/v1/cfdi/ocr-preview",
        files={"file": ("scan.pdf", content, "application/pdf")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["checksum_sha256"] == sha256(content).hexdigest()

    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor Demo",
            "amount": "100.00",
            "spent_on": "2026-08-07",
            "category": "Papeleria",
        },
    )
    assert expense.status_code == 201, expense.text
    uploaded = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={
            "attachment_type": "receipt",
            "ocr_preview_token": preview.json()["verification_token"],
        },
        files={"file": ("scan.pdf", content, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["checksum_sha256"] == sha256(content).hexdigest()
    assert uploaded.json()["content_type"] == "application/pdf"
    assert uploaded.json()["ocr_extraction"]["status"] == "succeeded"
    assert calls == 2
    stored = list(test_settings.upload_dir.rglob("*.pdf"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == content


def test_preview_returns_partial_read_for_manual_fields_without_bypassing_receiver_validation(
    client, monkeypatch, test_settings
) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            return _expense_response("COMERCIAL IAC", "CIA090819PW4")

        def detect_document_text(self, Document):
            return {"Blocks": []}

    test_settings.textract_enabled = True
    monkeypatch.setattr(TextractOcrService, "_client", lambda self: FakeClient())
    response = client.post(
        "/api/v1/cfdi/ocr-preview",
        files={"file": ("scan.jpg", b"\xff\xd8\xffimage", "image/jpeg")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["extracted_date"] is None
    assert response.json()["extracted_total"] is None
    assert response.json()["suggested_cfdi_uuid"] is None
    assert response.json()["verification_token"].startswith("v1.")


@pytest.mark.parametrize("error_code", ["AccessDeniedException", "BadDocumentException"])
def test_ocr_preview_failure_keeps_the_existing_user_message(
    client, monkeypatch, test_settings, error_code
) -> None:
    class FakeClient:
        def analyze_expense(self, Document):
            raise _aws_error(error_code)

        def detect_document_text(self, Document):
            raise _aws_error(error_code, "DetectDocumentText")

    test_settings.textract_enabled = True
    monkeypatch.setattr(TextractOcrService, "_client", lambda self: FakeClient())
    response = client.post(
        "/api/v1/cfdi/ocr-preview",
        files={"file": ("scan.jpg", b"\xff\xd8\xffimage", "image/jpeg")},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "OCR_UNREADABLE_DOCUMENT",
        "message": OCR_UNREADABLE_DOCUMENT_MESSAGE,
    }


@pytest.mark.parametrize("attachment_type", ["receipt", "other"])
def test_attachment_upload_reuses_ocr_preview_token(
    attachment_type,
    client,
    base_records,
    monkeypatch,
    test_settings,
) -> None:
    pdf_content = b"%PDF-1.4\ncontent\n%%EOF"
    test_settings.textract_enabled = True

    def fake_extract_expense(self, content, *, content_type, filename):
        return TextractOcrResult(
            raw_text=(
                "Razón Social: COMERCIAL IAC\n"
                "RFC: CIA090819PW4\n"
                "Folio Fiscal 11111111-2222-3333-4444-aaaaaaaaaaaa"
            ),
            extracted_total=Decimal("100.00"),
            extracted_date=date(2026, 8, 7),
            extracted_supplier="Proveedor Demo",
            suggested_cfdi_uuid="11111111-2222-3333-4444-AAAAAAAAAAAA",
            confidence=Decimal("98.50"),
            raw_response=None,
        )

    monkeypatch.setattr(TextractOcrService, "extract_expense", fake_extract_expense)
    preview = client.post(
        "/api/v1/cfdi/ocr-preview",
        files={"file": ("factura.pdf", pdf_content, "application/pdf")},
    )
    assert preview.status_code == 200, preview.text

    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor Demo",
            "amount": "100.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "papeleria",
            "cfdi_uuid": preview.json()["suggested_cfdi_uuid"],
            "cfdi_total": "100.00",
            "cfdi_currency": "MXN",
        },
    )
    assert expense.status_code == 201, expense.text

    def fail_if_called(self, content, *, content_type, filename):
        raise AssertionError("Textract should not run again when the preview token is valid")

    test_settings.textract_enabled = False
    monkeypatch.setattr(TextractOcrService, "extract_expense", fail_if_called)

    uploaded = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={
            "attachment_type": attachment_type,
            "ocr_preview_token": preview.json()["verification_token"],
        },
        files={"file": ("factura.pdf", pdf_content, "application/pdf")},
    )

    assert uploaded.status_code == 201, uploaded.text
    ocr = uploaded.json()["ocr_extraction"]
    assert ocr["suggested_cfdi_uuid"] == "11111111-2222-3333-4444-AAAAAAAAAAAA"
    assert ocr["extracted_total"] == "100.00"
