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
    accountant_user_id = _create_user(client, "accountant")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

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
        target_status="accounting_approved",
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
