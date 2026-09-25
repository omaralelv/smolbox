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
        raise CfdiParseError("CFDI XML root element is not cfdi:Comprobante")

    issuer = _find_first(root, "Emisor")
    receiver = _find_first(root, "Receptor")
    stamp = _find_first(root, "TimbreFiscalDigital")

    if stamp is None:
        warnings.append("CFDI stamp was not found")

    tax_summary = _parse_tax_summary(root, warnings)

    return CfdiParseResult(
        version=root.attrib.get("Version") or root.attrib.get("version"),
        uuid=_upper(_attr(stamp, "UUID")),
        issuer_rfc=_upper(_attr(issuer, "Rfc")),
        issuer_name=_attr(issuer, "Nombre"),
        receiver_rfc=_upper(_attr(receiver, "Rfc")),
        receiver_name=_attr(receiver, "Nombre"),
        subtotal=_parse_optional_decimal(root.attrib.get("SubTotal"), warnings, "CFDI subtotal"),
        total=_parse_decimal(root.attrib.get("Total"), warnings),
        currency=_upper(root.attrib.get("Moneda")),
        tax_amount=tax_summary["tax_amount"],
        tax_rate=tax_summary["tax_rate"],
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


def _find_direct_child(root: ElementTree.Element, local_name: str) -> ElementTree.Element | None:
    for element in root:
        if _local_name(element.tag) == local_name:
            return element
    return None


def _attr(element: ElementTree.Element | None, name: str) -> str | None:
    if element is None:
        return None
    return element.attrib.get(name) or element.attrib.get(name.lower())


def _upper(value: str | None) -> str | None:
    return value.strip().upper() if value and value.strip() else None


def _parse_decimal(value: str | None, warnings: list[str]) -> Decimal | None:
    if value is None:
        warnings.append("CFDI total was not found")
        return None
    return _parse_required_decimal(value, warnings, "CFDI total")


def _parse_required_decimal(value: str, warnings: list[str], field_name: str) -> Decimal | None:
    try:
        return Decimal(value)
    except InvalidOperation:
        warnings.append(f"{field_name} is not a valid decimal")
        return None


def _parse_optional_decimal(
    value: str | None,
    warnings: list[str],
    field_name: str,
) -> Decimal | None:
    if value is None:
        return None
    return _parse_required_decimal(value, warnings, field_name)


def _parse_tax_summary(
    root: ElementTree.Element,
    warnings: list[str],
) -> dict[str, Decimal | None]:
    taxes = _find_direct_child(root, "Impuestos")
    tax_transfers = _iva_transfers(taxes.iter() if taxes is not None else root.iter())
    tax_amount = _sum_tax_amounts(tax_transfers, warnings)
    tax_rate = _single_tax_rate(tax_transfers, warnings)

    if tax_amount is None and taxes is not None:
        tax_amount = _parse_optional_decimal(
            taxes.attrib.get("TotalImpuestosTrasladados"),
            warnings,
            "CFDI transferred tax total",
        )

    return {
        "tax_amount": tax_amount,
        "tax_rate": tax_rate,
    }


def _iva_transfers(elements) -> list[ElementTree.Element]:
    transfers = []
    for element in elements:
        if _local_name(element.tag) != "Traslado":
            continue
        if (element.attrib.get("Impuesto") or element.attrib.get("impuesto")) != "002":
            continue
        transfers.append(element)
    return transfers


def _sum_tax_amounts(
    transfers: list[ElementTree.Element],
    warnings: list[str],
) -> Decimal | None:
    amounts = [
        _parse_optional_decimal(
            transfer.attrib.get("Importe") or transfer.attrib.get("importe"),
            warnings,
            "CFDI transferred IVA amount",
        )
        for transfer in transfers
    ]
    valid_amounts = [amount for amount in amounts if amount is not None]
    if not valid_amounts:
        return None
    return sum(valid_amounts, Decimal(0))


def _single_tax_rate(
    transfers: list[ElementTree.Element],
    warnings: list[str],
) -> Decimal | None:
    rates = {
        rate * Decimal(100)
        for rate in (
            _parse_optional_decimal(
                transfer.attrib.get("TasaOCuota") or transfer.attrib.get("tasaOCuota"),
                warnings,
                "CFDI transferred IVA rate",
            )
            for transfer in transfers
            if (transfer.attrib.get("TipoFactor") or transfer.attrib.get("tipoFactor")) == "Tasa"
        )
        if rate is not None
    }
    if not rates:
        return None
    if len(rates) > 1:
        warnings.append("CFDI contains multiple IVA rates")
        return None
    return rates.pop().quantize(Decimal("0.01"))


def _parse_datetime(value: str | None, warnings: list[str]) -> datetime | None:
    if value is None:
        warnings.append("CFDI issue date was not found")
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        warnings.append("CFDI issue date is not a valid ISO datetime")
        return None
