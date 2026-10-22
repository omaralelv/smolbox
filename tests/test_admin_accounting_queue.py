from uuid import UUID

import pytest
from conftest import create_expense
from sqlalchemy import select
from test_frontend_adapter_api import (
    _attach_valid_cfdi,
    _auth_headers,
    _create_user,
    _transition,
)

from app.models.audit_log import AuditLog
from app.models.reimbursement_request import (
    AccountingQueueStatus,
    ReimbursementRequest,
    ReimbursementRequestStatus,
)


@pytest.fixture
def queue_scenario(client, base_records):
    expense = create_expense(client, base_records, amount="1500.00")
    _attach_valid_cfdi(client, expense["id"], "1500.00")
    actors = {}
    for label, role in [("admin", "admin"), ("first", "accountant"), ("second", "accountant")]:
        email = f"neutral.{label}@example.com"
        actors[label] = {"id": _create_user(client, role, email), "headers": _auth_headers(client, email)}
    submitted = _transition(client, base_records["request_id"], "submitted", actors["admin"]["id"])
    assert submitted.status_code == 200, submitted.text
    return {"request_id": base_records["request_id"], "expense_id": expense["id"], **actors}


def _queue_item(client, scenario, actor):
    response = client.get("/api/v1/frontend/bandeja/me", headers=scenario[actor]["headers"])
    assert response.status_code == 200, response.text
    return next(item for item in response.json() if item["backendId"] == scenario["request_id"])


def _open(client, scenario, actor):
    response = client.get(
        f"/api/v1/frontend/solicitudes/{scenario['request_id']}/me",
        headers=scenario[actor]["headers"],
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("already_taken", [False, True])
@pytest.mark.parametrize("request_stage", ["submitted", "under_accounting_review"])
def test_admin_repeated_reads_do_not_change_stage_owner_or_audit_log(
    client, queue_scenario, session_factory, already_taken, request_stage,
):
    scenario = queue_scenario
    if already_taken:
        _open(client, scenario, "first")
    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(scenario["request_id"]))
        request.status = ReimbursementRequestStatus(request_stage)
        session.commit()
        before_events = list(session.scalars(select(AuditLog.id).where(
            AuditLog.reimbursement_request_id == request.id,
        )))

    for _ in range(2):
        assert _open(client, scenario, "admin")["accountingQueueStatus"] == "single"
        detailed = client.get(
            f"/api/v1/reimbursement-requests/{scenario['request_id']}/detail/me",
            headers=scenario["admin"]["headers"],
        )
        assert detailed.status_code == 200, detailed.text
        assert _queue_item(client, scenario, "admin")["accountingQueueStatus"] == "single"

    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(scenario["request_id"]))
        assert request.status.value == request_stage
        assert request.accounting_queue_status == (
            AccountingQueueStatus.taken if already_taken else AccountingQueueStatus.single
        )
        assert request.accounting_queue_taken_by_user_id == (
            UUID(scenario["first"]["id"]) if already_taken else None
        )
        after_events = list(session.scalars(select(AuditLog.id).where(
            AuditLog.reimbursement_request_id == request.id,
        )))
        assert set(after_events) == set(before_events)


@pytest.mark.parametrize("already_taken", [False, True])
def test_admin_explicit_review_preserves_ownership_and_accountant_classification(
    client, queue_scenario, session_factory, already_taken,
):
    scenario = queue_scenario
    if already_taken:
        assert _open(client, scenario, "first")["accountingQueueStatus"] == "taken"

    response = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/transition/me",
        headers=scenario["admin"]["headers"],
        json={
            "target_status": "under_accounting_review", "action_key": "start_accounting_review",
            "note": "Inicio de revision solicitado por admin.",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "under_accounting_review"
    assert response.json()["accounting_queue_status"] == ("taken" if already_taken else "single")

    for _ in range(3):
        assert _open(client, scenario, "admin")["accountingQueueStatus"] == "single"
    assert _queue_item(client, scenario, "first")["accountingQueueStatus"] == (
        "taken" if already_taken else "single"
    )
    assert _queue_item(client, scenario, "second")["accountingQueueStatus"] == (
        "taken_other" if already_taken else "single"
    )

    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(scenario["request_id"]))
        assert request.accounting_queue_taken_by_user_id == (
            UUID(scenario["first"]["id"]) if already_taken else None
        )
        events = session.scalars(select(AuditLog).where(
            AuditLog.reimbursement_request_id == request.id,
            AuditLog.actor_user_id == UUID(scenario["admin"]["id"]),
        )).all()
        assert not any(event.action == "accounting_request_taken" for event in events)
        assert any(event.action == "request_status_changed"
                   and event.to_status == "under_accounting_review" for event in events)
        assert any(event.action == "button_selected"
                   and event.event_payload.get("action_key") == "start_accounting_review"
                   for event in events)

    # The first real accountant still claims the request, without admin becoming its owner.
    assert _open(client, scenario, "first")["accountingQueueStatus"] == "taken"
    assert _open(client, scenario, "second")["accountingQueueStatus"] == "taken_other"
    edited = client.patch(
        f"/api/v1/expenses/{scenario['expense_id']}/review/me",
        headers=scenario["admin"]["headers"],
        json={"cfdi_tax_rate": "8.00", "note": "Impuesto revisado por admin."},
    )
    assert edited.status_code == 200, edited.text
    comment = client.post(
        f"/api/v1/expenses/{scenario['expense_id']}/observation/me",
        headers=scenario["admin"]["headers"],
        json={"note": "Comentario de admin sin tomar la solicitud."},
    )
    assert comment.status_code == 200, comment.text
    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(scenario["request_id"]))
        assert request.accounting_queue_status == AccountingQueueStatus.taken
        assert str(request.accounting_queue_taken_by_user_id) == scenario["first"]["id"]
    assert _queue_item(client, scenario, "admin")["accountingQueueStatus"] == "single"
    assert _queue_item(client, scenario, "first")["accountingQueueStatus"] == "taken"
    assert _queue_item(client, scenario, "second")["accountingQueueStatus"] == "taken_other"
