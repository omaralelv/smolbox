from conftest import create_expense
from fastapi.testclient import TestClient


def test_can_patch_core_records(client: TestClient, base_records: dict[str, str]) -> None:
    store = client.patch(
        f"/api/v1/stores/{base_records['store_id']}",
        json={"name": "Tienda Centro Actualizada", "assigned_accountant": "Nuevo Contador"},
    )
    assert store.status_code == 200, store.text
    assert store.json()["name"] == "Tienda Centro Actualizada"
    assert store.json()["assigned_accountant"] == "Nuevo Contador"

    period = client.patch(
        f"/api/v1/periods/{base_records['period_id']}",
        json={"ends_on": "2026-09-05"},
    )
    assert period.status_code == 200, period.text
    assert period.json()["ends_on"] == "2026-09-05"

    request = client.patch(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}",
        json={"reported_total": "125.00", "notes": "Monto corregido por tienda"},
    )
    assert request.status_code == 200, request.text
    assert request.json()["reported_total"] == "125.00"
    assert request.json()["notes"] == "Monto corregido por tienda"

    expense = create_expense(client, base_records, amount="123.45")
    updated_expense = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"amount": "125.00", "category": "limpieza"},
    )
    assert updated_expense.status_code == 200, updated_expense.text
    assert updated_expense.json()["amount"] == "125.00"
    assert updated_expense.json()["category"] == "limpieza"

    user = client.post(
        "/api/v1/users/",
        json={
            "email": "usuario.edicion@example.com",
            "full_name": "Usuario Edicion",
            "role": "store",
        },
    )
    assert user.status_code == 201, user.text

    updated_user = client.patch(
        f"/api/v1/users/{user.json()['id']}",
        json={"role": "accountant", "full_name": "Usuario Contable"},
    )
    assert updated_user.status_code == 200, updated_user.text
    assert updated_user.json()["role"] == "accountant"
    assert updated_user.json()["full_name"] == "Usuario Contable"

    deactivated_user = client.post(f"/api/v1/users/{user.json()['id']}/deactivate")
    assert deactivated_user.status_code == 200, deactivated_user.text
    assert deactivated_user.json()["is_active"] is False


def test_rejects_edit_after_submission(client: TestClient, base_records: dict[str, str]) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    receipt = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text

    user = client.post(
        "/api/v1/users/",
        json={
            "email": "tienda.submit@example.com",
            "full_name": "Tienda Submit",
            "role": "store",
        },
    )
    assert user.status_code == 201, user.text

    assignment = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text

    submitted = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition",
        json={
            "target_status": "submitted",
            "actor_user_id": user.json()["id"],
            "note": "Enviar",
        },
    )
    assert submitted.status_code == 200, submitted.text

    blocked = client.patch(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}",
        json={"notes": "Cambio tardio"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "REQUEST_NOT_EDITABLE"
