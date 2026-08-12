from conftest import create_expense
from fastapi.testclient import TestClient


def _create_user(client: TestClient, role: str) -> str:
    response = client.post(
        "/api/v1/users/",
        json={
            "email": f"{role}@example.com",
            "full_name": f"{role.title()} Demo",
            "role": role,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _assign_user_to_store(client: TestClient, store_id: str, user_id: str, role: str) -> None:
    response = client.post(
        f"/api/v1/stores/{store_id}/users",
        json={"user_id": user_id, "role": role},
    )
    assert response.status_code == 201, response.text


def _transition(
    client: TestClient,
    request_id: str,
    *,
    target_status: str,
    actor_user_id: str,
):
    return client.post(
        f"/api/v1/reimbursement-requests/{request_id}/transition",
        json={
            "target_status": target_status,
            "actor_user_id": actor_user_id,
            "note": f"Move to {target_status}",
        },
    )


def test_request_moves_through_submission_and_accounting_review(
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

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    accountant_user_id = _create_user(client, "accountant")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    authorization_review = _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    )
    assert authorization_review.status_code == 200, authorization_review.text
    assert authorization_review.json()["status"] == "authorization_review"

    authorized = _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["status"] == "authorized"

    review = _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=accountant_user_id,
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "under_accounting_review"

    premature_approval = _transition(
        client,
        base_records["request_id"],
        target_status="accounting_reviewed",
        actor_user_id=accountant_user_id,
    )
    assert premature_approval.status_code == 409
    assert premature_approval.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200
    actions = {event["action"] for event in audit_events.json()}
    assert "request_status_changed" in actions
    assert "expense_attachment_uploaded" in actions


def test_required_expense_authorization_blocks_request(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor con Autorizacion",
            "amount": "1500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert expense.status_code == 201, expense.text
    receipt = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    authorization_review = _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    )
    assert authorization_review.status_code == 200, authorization_review.text

    blocked = _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    authorized_expense = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/authorize",
        json={"actor_user_id": authorizer_user_id, "note": "Autorizado por area"},
    )
    assert authorized_expense.status_code == 200, authorized_expense.text
    assert authorized_expense.json()["authorized_at"] is not None

    authorized = _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["status"] == "authorized"


def test_accounting_can_remove_expense_with_reason(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    first_expense = create_expense(client, base_records, amount="1000.00")
    second_expense = create_expense(client, base_records, amount="500.00")
    for expense in [first_expense, second_expense]:
        receipt = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            data={"attachment_type": "receipt"},
            files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
        )
        assert receipt.status_code == 201, receipt.text

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    accountant_user_id = _create_user(client, "accountant")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    assert _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=accountant_user_id,
    ).status_code == 200

    removed = client.post(
        f"/api/v1/expenses/{second_expense['id']}/remove",
        json={
            "actor_user_id": accountant_user_id,
            "reason": "Factura no procede",
            "adjust_reported_total": True,
        },
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "removed"
    assert removed.json()["removal_reason"] == "Factura no procede"

    summary = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/validation-summary"
    )
    assert summary.status_code == 200
    assert summary.json()["expense_count"] == 1
    assert summary.json()["calculated_total"] == "1000.00"
    assert summary.json()["reported_total"] == "1000.00"
    assert second_expense["id"] in summary.json()["removed_expense_ids"]

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200
    assert "expense_removed_from_request" in {event["action"] for event in audit_events.json()}
