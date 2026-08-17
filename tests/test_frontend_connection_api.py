from conftest import create_expense
from fastapi.testclient import TestClient

from app.main import app as main_app


def _auth_headers(client: TestClient, email: str, password: str = "secret-password") -> dict[str, str]:
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _cfdi_xml(uuid: str, total: str = "123.45") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Fecha="2026-08-07T12:10:00"
    Total="{total}"
    Moneda="MXN">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor Demo"/>
  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="Smolbox Demo"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
""".encode()


def test_frontend_origin_is_allowed_by_main_app() -> None:
    with TestClient(main_app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_work_queue_and_request_detail_include_frontend_payload(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "frontend.store@example.com",
            "full_name": "Frontend Store",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text
    assignment = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text
    headers = _auth_headers(client, "frontend.store@example.com")

    expense = create_expense(client, base_records)
    receipt = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    cfdi = client.post(
        f"/api/v1/expenses/{expense['id']}/cfdi/validate",
        files={
            "file": (
                "invoice.xml",
                _cfdi_xml("11111111-2222-3333-4444-AAAAAAAAAAAA"),
                "application/xml",
            )
        },
    )
    assert cfdi.status_code == 200, cfdi.text
    request_attachment = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/attachments",
        data={"attachment_type": "cash_box_format"},
        files={"file": ("caja.csv", b"merchant,amount\nProveedor Demo,123.45\n", "text/csv")},
    )
    assert request_attachment.status_code == 201, request_attachment.text

    queue = client.get("/api/v1/work-queue/me", headers=headers)
    assert queue.status_code == 200, queue.text
    assert queue.json()[0]["id"] == base_records["request_id"]
    assert queue.json()[0]["folio"]
    assert queue.json()[0]["store"]["code"] == "T001"
    assert queue.json()[0]["expense_count"] == 1
    assert "submit_request" in queue.json()[0]["available_actions"]

    detail = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/detail/me",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == base_records["request_id"]
    assert body["folio"] == queue.json()[0]["folio"]
    assert body["store"]["code"] == "T001"
    assert body["period"]["id"] == base_records["period_id"]
    assert body["validation_summary"]["expense_count"] == 1
    assert body["attachments"][0]["id"] == request_attachment.json()["id"]
    assert body["expenses"][0]["attachments"][0]["id"] == receipt.json()["id"]
    assert body["expenses"][0]["current_cfdi_validation"]["is_valid"] is True
    assert body["expenses"][0]["current_cfdi_validation"]["uuid"] == (
        "11111111-2222-3333-4444-AAAAAAAAAAAA"
    )
    assert "submit_request" in body["available_actions"]
