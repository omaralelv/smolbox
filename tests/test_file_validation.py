from io import BytesIO
from zipfile import ZipFile

import pytest

from app.models.attachment import AttachmentType
from app.services.file_validation import InvalidAttachment, detect_attachment_content_type


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
