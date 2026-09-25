from uuid import uuid4

from conftest import create_expense
from fastapi.testclient import TestClient


def _cfdi_xml(amount: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Fecha="2026-08-07T12:10:00"
    Total="{amount}"
    Moneda="MXN">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor Demo"/>
  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="Smolbox Demo"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid4()}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
""".encode()


def test_automated_review_returns_machine_and_human_steps(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    receipt = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text

    review = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/automated-review"
    )

    assert review.status_code == 200, review.text
    body = review.json()
    assert body["request_id"] == base_records["request_id"]
    assert body["overall_status"] == "blocked"

    automatic_steps = {step["code"]: step for step in body["automatic_steps"]}
    assert automatic_steps["receipt_check"]["status"] == "passed"
    assert automatic_steps["cfdi_validation"]["status"] == "blocked"
    assert automatic_steps["cfdi_validation"]["blocking"] is True
    assert automatic_steps["total_balance"]["status"] == "passed"
    assert automatic_steps["period_check"]["status"] == "passed"
    assert automatic_steps["ocr_extraction"]["status"] == "not_configured"
    assert automatic_steps["sap_policy_data"]["status"] == "blocked"

    human_steps = {step["code"]: step for step in body["human_steps"]}
    assert "manager_approval" in human_steps
    assert "direction_approval" in human_steps
    assert "payment_confirmation" in human_steps

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200
    assert "automated_review_completed" in {event["action"] for event in audit_events.json()}


def test_automated_review_treats_missing_receipt_as_non_blocking(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    cfdi = client.post(
        f"/api/v1/expenses/{expense['id']}/cfdi/validate",
        files={"file": ("invoice.xml", _cfdi_xml("1500.00"), "application/xml")},
    )
    assert cfdi.status_code == 200, cfdi.text
    assert cfdi.json()["is_valid"] is True

    review = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/automated-review"
    )

    assert review.status_code == 200, review.text
    automatic_steps = {step["code"]: step for step in review.json()["automatic_steps"]}
    assert automatic_steps["receipt_check"]["status"] == "attention"
    assert automatic_steps["receipt_check"]["blocking"] is False
    assert automatic_steps["cfdi_validation"]["status"] == "passed"
