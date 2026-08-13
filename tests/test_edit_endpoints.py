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
    authorizer = client.post(
        "/api/v1/users/",
        json={
            "email": "autorizador.submit@example.com",
            "full_name": "Autorizador Submit",
            "role": "authorizer",
        },
    )
    assert authorizer.status_code == 201, authorizer.text

    assignment = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text
    authorizer_assignment = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": authorizer.json()["id"], "role": "authorizer"},
    )
    assert authorizer_assignment.status_code == 201, authorizer_assignment.text

    submitted = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition",
        json={
            "target_status": "submitted",
            "actor_user_id": user.json()["id"],
            "note": "Enviar",
        },
    )
    assert submitted.status_code == 200, submitted.text

    blocked_request = client.patch(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}",
        json={"notes": "Cambio tardio"},
    )
    assert blocked_request.status_code == 409
    assert blocked_request.json()["detail"]["code"] == "REQUEST_NOT_EDITABLE"

    blocked_expense_edit = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"category": "cambio-tardio"},
    )
    assert blocked_expense_edit.status_code == 409
    assert blocked_expense_edit.json()["detail"]["code"] == "REQUEST_NOT_EDITABLE"

    blocked_expense_create = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor Tardio",
            "amount": "10.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "tardio",
        },
    )
    assert blocked_expense_create.status_code == 409
    assert blocked_expense_create.json()["detail"]["code"] == "REQUEST_NOT_EDITABLE"

    blocked_attachment = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("late-receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert blocked_attachment.status_code == 409
    assert blocked_attachment.json()["detail"]["code"] == "REQUEST_NOT_EDITABLE"

    blocked_cfdi = client.post(
        f"/api/v1/expenses/{expense['id']}/cfdi/validate",
        files={"file": ("late.xml", b"<xml />", "application/xml")},
    )
    assert blocked_cfdi.status_code == 409
    assert blocked_cfdi.json()["detail"]["code"] == "REQUEST_NOT_EDITABLE"

    authorization_review = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition",
        json={
            "target_status": "authorization_review",
            "actor_user_id": authorizer.json()["id"],
            "note": "Revisar",
        },
    )
    assert authorization_review.status_code == 200, authorization_review.text

    correction = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition",
        json={
            "target_status": "correction_required",
            "actor_user_id": authorizer.json()["id"],
            "note": "Regresar a corrección",
        },
    )
    assert correction.status_code == 200, correction.text

    corrected_expense = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"category": "corregido"},
    )
    assert corrected_expense.status_code == 200, corrected_expense.text
    assert corrected_expense.json()["category"] == "corregido"
