from datetime import datetime
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from app.schemas.cfdi import CfdiParseResult


class CfdiParseError(ValueError):
    pass


def parse_cfdi_xml(xml_bytes: bytes) -> CfdiParseResult:
    if not xml_bytes.strip():
        raise CfdiParseError("CFDI XML file is empty")

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise CfdiParseError("CFDI XML file could not be parsed") from exc

    warnings: list[str] = []
    if _local_name(root.tag) != "Comprobante":
        warnings.append("Root element is not cfdi:Comprobante")

    issuer = _find_first(root, "Emisor")
    receiver = _find_first(root, "Receptor")
    stamp = _find_first(root, "TimbreFiscalDigital")

    if stamp is None:
        warnings.append("CFDI stamp was not found")

    return CfdiParseResult(
        version=root.attrib.get("Version") or root.attrib.get("version"),
        uuid=_attr(stamp, "UUID"),
        issuer_rfc=_attr(issuer, "Rfc"),
        issuer_name=_attr(issuer, "Nombre"),
        receiver_rfc=_attr(receiver, "Rfc"),
        receiver_name=_attr(receiver, "Nombre"),
        total=_parse_decimal(root.attrib.get("Total"), warnings),
        currency=root.attrib.get("Moneda"),
        issued_at=_parse_datetime(root.attrib.get("Fecha"), warnings),
        payment_method=root.attrib.get("MetodoPago"),
        warnings=warnings,
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _find_first(root: ElementTree.Element, local_name: str) -> ElementTree.Element | None:
    for element in root.iter():
        if _local_name(element.tag) == local_name:
            return element
    return None


def _attr(element: ElementTree.Element | None, name: str) -> str | None:
    if element is None:
        return None
    return element.attrib.get(name) or element.attrib.get(name.lower())


def _parse_decimal(value: str | None, warnings: list[str]) -> Decimal | None:
    if value is None:
        warnings.append("CFDI total was not found")
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        warnings.append("CFDI total is not a valid decimal")
        return None


def _parse_datetime(value: str | None, warnings: list[str]) -> datetime | None:
    if value is None:
        warnings.append("CFDI issue date was not found")
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        warnings.append("CFDI issue date is not a valid ISO datetime")
        return None
