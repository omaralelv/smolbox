from conftest import create_expense
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.attachment import Attachment, AttachmentType
from app.models.cfdi_validation import CfdiValidation


def _cfdi_xml(
    uuid: str,
    *,
    currency_attribute: str = 'Moneda="MXN"',
    receiver_attribute: str = 'Rfc="BBB010101BBB"',
) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Fecha="2026-08-07T12:10:00"
    Total="123.45"
    {currency_attribute}>
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor Demo"/>
  <cfdi:Receptor {receiver_attribute} Nombre="Smolbox Demo"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
""".encode()


def _validate(client: TestClient, expense_id: str, content: bytes):
    return client.post(
        f"/api/v1/expenses/{expense_id}/cfdi/validate",
        files={"file": ("invoice.xml", content, "application/xml")},
    )


def test_persists_cfdi_validation_and_rejects_duplicate_uuid(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    first_expense = create_expense(client, base_records)
    uuid = "11111111-2222-3333-4444-555555555555"
    validation = _validate(client, str(first_expense["id"]), _cfdi_xml(uuid))
    assert validation.status_code == 200, validation.text
    assert validation.json()["is_valid"] is True

    persisted_expense = client.get(f"/api/v1/expenses/{first_expense['id']}")
    assert persisted_expense.status_code == 200
    assert persisted_expense.json()["cfdi_uuid"] == uuid.upper()

    with session_factory() as session:
        persisted_validation = session.scalar(select(CfdiValidation))
        assert persisted_validation is not None
        assert persisted_validation.is_valid is True
        assert persisted_validation.is_current is True
        attachment = session.get(Attachment, persisted_validation.attachment_id)
        assert attachment is not None
        assert attachment.attachment_type == AttachmentType.cfdi_xml

    second_expense = create_expense(client, base_records)
    duplicate = _validate(client, str(second_expense["id"]), _cfdi_xml(uuid.lower()))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "DUPLICATE_CFDI_UUID"


def test_missing_cfdi_fields_are_invalid_and_size_limit_is_enforced(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    expense = create_expense(client, base_records)
    uuid = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    missing_fields = _validate(
        client,
        str(expense["id"]),
        _cfdi_xml(uuid, currency_attribute="", receiver_attribute=""),
    )
    assert missing_fields.status_code == 200, missing_fields.text
    assert missing_fields.json()["is_valid"] is False
    assert {issue["code"] for issue in missing_fields.json()["issues"]} >= {
        "missing_currency",
        "missing_receiver_rfc",
    }

    with session_factory() as session:
        validation = session.scalar(select(CfdiValidation))
        assert validation is not None
        assert validation.is_valid is False

    too_large = client.post(
        "/api/v1/cfdi/parse",
        files={"file": ("large.xml", b"x" * 4097, "application/xml")},
    )
    assert too_large.status_code == 413

    malformed = client.post(
        "/api/v1/cfdi/parse",
        files={"file": ("malformed.xml", b"<broken>", "application/xml")},
    )
    assert malformed.status_code == 422
