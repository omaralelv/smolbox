from io import BytesIO
from zipfile import ZipFile

import pytest

from app.models.attachment import AttachmentType
from app.services.file_validation import (
    InvalidAttachment,
    detect_attachment_content_type,
    prepare_attachment_for_processing,
)
from app.services.pdf_normalization import PdfNormalizationError


def _xlsx_bytes() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "<Types />")
        workbook.writestr("xl/workbook.xml", "<workbook />")
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "content", "expected_type"),
    [
        (
            "cash-box.xlsx",
            _xlsx_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "cash-box.xls",
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1legacy-workbook",
            "application/vnd.ms-excel",
        ),
        ("cash-box.csv", b"category,amount\npaper,100.00\n", "text/csv"),
    ],
)
def test_detects_supported_cash_box_formats(
    filename: str,
    content: bytes,
    expected_type: str,
) -> None:
    detected = detect_attachment_content_type(
        filename,
        content,
        AttachmentType.cash_box_format,
    )
    assert detected == expected_type


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("fake.pdf", b"plain text"),
        ("fake.xlsx", b"not a ZIP workbook"),
        ("fake.xml", b"<document />"),
        ("binary.csv", b"value\x00payload"),
    ],
)
def test_rejects_files_disguised_with_allowed_extensions(
    filename: str,
    content: bytes,
) -> None:
    attachment_type = (
        AttachmentType.receipt
        if filename.endswith(".pdf")
        else AttachmentType.cfdi_xml
        if filename.endswith(".xml")
        else AttachmentType.cash_box_format
    )
    with pytest.raises(InvalidAttachment):
        detect_attachment_content_type(filename, content, attachment_type)


@pytest.mark.parametrize(
    ("filename", "content", "attachment_type"),
    [
        ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", AttachmentType.receipt),
        ("receipt.jpg", b"\xff\xd8\xffimage", AttachmentType.receipt),
        ("receipt.png", b"\x89PNG\r\n\x1a\nimage", AttachmentType.receipt),
        ("invoice.xml", b"<Comprobante />", AttachmentType.cfdi_xml),
        ("cash.xlsx", _xlsx_bytes(), AttachmentType.cash_box_format),
    ],
)
def test_valid_uploads_are_not_rewritten(monkeypatch, filename, content, attachment_type) -> None:
    def unexpected_normalization(*args, **kwargs):
        raise AssertionError("Valid uploads must follow the existing path")

    monkeypatch.setattr(
        "app.services.file_validation.normalize_pdf_for_processing", unexpected_normalization
    )
    content_type, processing_content = prepare_attachment_for_processing(
        filename, content, attachment_type, max_bytes=1024 * 1024
    )
    assert content_type == detect_attachment_content_type(filename, content, attachment_type)
    assert processing_content is content


@pytest.mark.parametrize("attachment_type", [AttachmentType.receipt, AttachmentType.other])
def test_failed_recovery_preserves_the_original_validation_message(attachment_type) -> None:
    content = b"^{doc_title = test}\r\n%PDF-1.4\ncorrupted\n%%EOF"
    with pytest.raises(InvalidAttachment) as original:
        detect_attachment_content_type("invoice.pdf", content, attachment_type)
    with pytest.raises(InvalidAttachment) as recovered:
        prepare_attachment_for_processing(
            "invoice.pdf", content, attachment_type, max_bytes=1024 * 1024
        )
    assert str(recovered.value) == str(original.value)
    assert isinstance(recovered.value.__cause__, PdfNormalizationError)


@pytest.mark.parametrize("attachment_type", [AttachmentType.cash_box_format, AttachmentType.cfdi_xml])
def test_pdf_recovery_does_not_bypass_other_attachment_types(monkeypatch, attachment_type) -> None:
    def unexpected_normalization(*args, **kwargs):
        raise AssertionError("Only PDF evidence can be recovered")

    monkeypatch.setattr(
        "app.services.file_validation.normalize_pdf_for_processing", unexpected_normalization
    )
    with pytest.raises(InvalidAttachment):
        prepare_attachment_for_processing(
            "invoice.pdf", b"prefix%PDF-1.4\n%%EOF", attachment_type, max_bytes=1024 * 1024
        )
