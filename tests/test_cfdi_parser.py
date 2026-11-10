from decimal import Decimal

import pytest

from app.services.cfdi_parser import CfdiParseError, parse_cfdi_xml

CFDI_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Fecha="2026-08-07T12:10:00"
    SubTotal="100.00"
    Total="123.45"
    Moneda="MXN"
    MetodoPago="PUE">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor Demo"/>
  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="Smolbox Demo"/>
  <cfdi:Impuestos TotalImpuestosTrasladados="23.45">
    <cfdi:Traslados>
      <cfdi:Traslado Base="100.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="16.00"/>
      <cfdi:Traslado Base="93.13" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.080000" Importe="7.45"/>
    </cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="11111111-2222-3333-4444-555555555555"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
"""


def test_parse_cfdi_extracts_core_fields() -> None:
    result = parse_cfdi_xml(CFDI_XML)

    assert result.uuid == "11111111-2222-3333-4444-555555555555"
    assert result.issuer_rfc == "AAA010101AAA"
    assert result.receiver_rfc == "BBB010101BBB"
    assert result.subtotal == Decimal("100.00")
    assert result.total == Decimal("123.45")
    assert result.currency == "MXN"
    assert result.tax_amount == Decimal("23.45")
    assert result.tax_rate is None
    assert result.issued_at is not None
    assert result.warnings == ["CFDI contains multiple IVA rates"]


def test_parse_cfdi_extracts_single_iva_rate() -> None:
    result = parse_cfdi_xml(
        CFDI_XML.replace(
            b"""      <cfdi:Traslado Base="93.13" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.080000" Importe="7.45"/>
""",
            b"",
        ).replace(b'TotalImpuestosTrasladados="23.45"', b'TotalImpuestosTrasladados="16.00"')
    )

    assert result.tax_amount == Decimal("16.00")
    assert result.tax_rate == Decimal("16.00")


def test_parse_cfdi_rejects_non_cfdi_root() -> None:
    with pytest.raises(CfdiParseError, match="root element"):
        parse_cfdi_xml(b"<document />")
