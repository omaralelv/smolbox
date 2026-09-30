from datetime import date
from decimal import Decimal

import pytest

from app.services.textract_ocr import (
    TextractOcrResult,
    TextractOcrService,
    _parse_analyze_expense_response,
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
                            "Text": (
                                "Folio Fiscal 11111111 2222 3333 4444 "
                                "aaaaaaaaaaaa"
                            ),
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
