from conftest import create_expense
from fastapi.testclient import TestClient


def test_frontend_context_and_bandeja_use_ui_shape(
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
    expense = create_expense(client, base_records, amount="56.00", spent_on="2026-08-07")
    assert expense["id"]

    headers = _auth_headers(client, "frontend.store@example.com")

    context = client.get("/api/v1/frontend/context/me", headers=headers)
    assert context.status_code == 200, context.text
    context_body = context.json()
    assert context_body["currentRole"] == "tienda"
    assert context_body["backendRole"] == "store"
    assert context_body["tienda"] == "T001"

    bandeja = client.get("/api/v1/frontend/bandeja/me", headers=headers)
    assert bandeja.status_code == 200, bandeja.text
    items = bandeja.json()
    assert len(items) == 1
    item = items[0]
    assert item["id"] == item["folio"]
    assert item["backendId"] == base_records["request_id"]
    assert item["tienda"] == "T001"
    assert item["status"] == "En captura"
    assert item["montoTotal"] == 56.0
    assert item["gastos"][0]["monto"] == 56.0
    assert item["gastos"][0]["tipo"]
    assert "backendId" in item["gastos"][0]
    assert item["availableActions"] == [
        "edit_request",
        "add_expense",
        "upload_request_attachment",
        "submit_request",
    ]
    assert item["actionLabels"]["add_expense"] == "Añadir gasto"


def test_frontend_can_create_request_and_lookup_by_folio(client: TestClient) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "frontend.create@example.com",
            "full_name": "Frontend Create",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text
    store = client.post(
        "/api/v1/stores/",
        json={
            "code": "T998",
            "name": "Tienda Frontend",
            "manager_name": "Karen Ponce Hernandez",
            "bank_account": "101328508",
            "state_region": "CDMX",
        },
    )
    assert store.status_code == 201, store.text
    assignment = client.post(
        f"/api/v1/stores/{store.json()['id']}/users",
        json={"user_id": user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text
    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Agosto Frontend",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-31",
        },
    )
    assert period.status_code == 201, period.text

    headers = _auth_headers(client, "frontend.create@example.com")
    created = client.post(
        "/api/v1/frontend/solicitudes/me",
        headers=headers,
        json={
            "tienda": "T998",
            "montoTotal": "56.00",
            "gastos": [
                {
                    "fecha": "07/08/2026",
                    "categoria": "Papelería",
                    "monto": "56.00",
                    "folio": "5FB2822E-396D-4725-8521-CDC4BDD20CCF",
                    "observaciones": "Compra demo",
                    "requiresAuthorization": True,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["id"].startswith("T998-")
    assert created_body["tienda"] == "T998"
    assert created_body["gerente"] == "Karen Ponce Hernandez"
    assert created_body["cuentaBancaria"] == "101328508"
    assert created_body["montoTotal"] == 56.0
    assert created_body["gastos"][0]["nombre"] == "Gasto - Papelería"
    assert created_body["gastos"][0]["folio"] == "5FB2822E-396D-4725-8521-CDC4BDD20CCF"
    assert created_body["gastos"][0]["requiresAuthorization"] is True

    detail = client.get(
        f"/api/v1/frontend/solicitudes/{created_body['folio']}/me",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["backendId"] == created_body["backendId"]


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
