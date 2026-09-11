from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from app.models.attachment import AttachmentType


class InvalidAttachment(ValueError):
    pass


def detect_attachment_content_type(
    filename: str,
    content: bytes,
    attachment_type: AttachmentType,
) -> str:
    extension = Path(filename).suffix.lower()

    if attachment_type == AttachmentType.cash_box_format:
        return _detect_cash_box_format(extension, content)
    if attachment_type == AttachmentType.receipt:
        return _detect_receipt(extension, content)
    if attachment_type == AttachmentType.cfdi_xml:
        return _detect_cfdi_xml(extension, content)

    raise InvalidAttachment("The 'other' attachment type is not configured for this MVP")


def _detect_cash_box_format(extension: str, content: bytes) -> str:
    if extension == ".xlsx":
        try:
            with ZipFile(BytesIO(content)) as workbook:
                names = set(workbook.namelist())
        except BadZipFile as exc:
            raise InvalidAttachment("The XLSX file is not a valid Office workbook") from exc
        if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
            raise InvalidAttachment("The XLSX file does not contain a workbook")
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    if extension == ".xls":
        if not content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise InvalidAttachment("The XLS file does not have a valid OLE signature")
        return "application/vnd.ms-excel"

    if extension == ".csv":
        if b"\x00" in content:
            raise InvalidAttachment("The CSV file contains binary data")
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidAttachment("The CSV file must be UTF-8 text") from exc
        return "text/csv"

    raise InvalidAttachment("Cash box formats must be XLSX, XLS, or CSV")


def _detect_receipt(extension: str, content: bytes) -> str:
    if extension == ".pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
            raise InvalidAttachment("The PDF file does not have a valid signature")
        return "application/pdf"
    if extension in {".jpg", ".jpeg"}:
        if not content.startswith(b"\xff\xd8\xff"):
            raise InvalidAttachment("The JPEG file does not have a valid signature")
        return "image/jpeg"
    if extension == ".png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise InvalidAttachment("The PNG file does not have a valid signature")
        return "image/png"
    raise InvalidAttachment("Receipts must be PDF, JPEG, or PNG")


def _detect_cfdi_xml(extension: str, content: bytes) -> str:
    if extension != ".xml":
        raise InvalidAttachment("CFDI evidence must use the .xml extension")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise InvalidAttachment("The CFDI XML could not be parsed") from exc
    if root.tag.rsplit("}", maxsplit=1)[-1] != "Comprobante":
        raise InvalidAttachment("The XML root element is not cfdi:Comprobante")
    return "application/xml"
