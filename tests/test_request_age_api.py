from datetime import UTC, datetime
from uuid import UUID

import pytest
from conftest import authenticated_audit_headers, create_expense
from sqlalchemy import func, select
from test_frontend_adapter_api import _attach_valid_cfdi, _transition

from app.api.v1.endpoints import frontend, reimbursement_requests
from app.models.audit_log import AuditLog
from app.models.expense import Expense, ExpenseStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.services import workflow


class Clock(datetime):
    current = datetime(2026, 10, 28, 18, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls.current.astimezone(tz or UTC)


@pytest.fixture
def aged_request(client, base_records, session_factory, monkeypatch):
    expense = create_expense(client, base_records, amount="1500.00")
    _attach_valid_cfdi(client, expense["id"], "1500.00")
    headers = authenticated_audit_headers(client)
    admin = client.get("/api/v1/frontend/context/me", headers=headers).json()["usuario"]["id"]
    response = _transition(client, base_records["request_id"], "submitted", admin)
    assert response.status_code == 200, response.text
    assert response.json()["first_submitted_at"]
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.first_submitted_at = datetime(2026, 10, 23, 18, tzinfo=UTC)
        request.submitted_at = datetime(2026, 10, 27, 18, tzinfo=UTC)
        db.commit()
    Clock.current = datetime(2026, 10, 28, 18, tzinfo=UTC)
    monkeypatch.setattr(frontend, "datetime", Clock)
    monkeypatch.setattr(reimbursement_requests, "datetime", Clock)
    monkeypatch.setattr(workflow, "datetime", Clock)
    return {**base_records, "expense_id": expense["id"], "headers": headers}


def _queue(client, scenario, historical=False):
    response = client.get(
        "/api/v1/frontend/historico/me" if historical else "/api/v1/frontend/bandeja/me",
        headers=scenario["headers"],
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_age_is_returned_per_request_and_reads_never_take_or_mutate_it(
    client, aged_request, session_factory,
):
    scenario = aged_request
    with session_factory() as db:
        before = db.scalar(select(func.count()).select_from(AuditLog))
    item = _queue(client, scenario)[0]
    assert item["firstSubmittedAt"].startswith("2026-10-23T18:00:00")
    assert item["elapsedDays"] == 5
    assert item["ageStoppedAt"] is None
    assert item["accountingQueueStatus"] == "single"
    for _ in range(2):
        response = client.get(
            f"/api/v1/frontend/solicitudes/{scenario['request_id']}/me", headers=scenario["headers"],
        )
        assert response.status_code == 200, response.text
        assert response.json()["elapsedDays"] == 5
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AuditLog)) == before
        request = db.get(ReimbursementRequest, UUID(scenario["request_id"]))
        assert request.accounting_queue_taken_by_user_id is None
        assert request.status == ReimbursementRequestStatus.submitted


def test_payment_stops_the_counter_and_closing_later_does_not_extend_it(
    client, aged_request, session_factory,
):
    scenario = aged_request
    with session_factory() as db:
        db.get(ReimbursementRequest, UUID(scenario["request_id"])).status = (
            ReimbursementRequestStatus.approved_for_payment
        )
        db.commit()
    assert _queue(client, scenario)[0]["elapsedDays"] == 5
    paid = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/payments/me",
        headers=scenario["headers"], json={"reference": "AGE-TEST", "payment_method": "transfer"},
    )
    assert paid.status_code == 201, paid.text
    assert _queue(client, scenario) == []
    historical = _queue(client, scenario, historical=True)[0]
    assert historical["elapsedDays"] == 5
    assert historical["ageStoppedAt"].startswith("2026-10-28T18:00:00")
    Clock.current = datetime(2026, 11, 5, 18, tzinfo=UTC)
    closed = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/transition/me",
        headers=scenario["headers"], json={"target_status": "closed", "note": "Cierre posterior"},
    )
    assert closed.status_code == 200, closed.text
    historical = _queue(client, scenario, historical=True)[0]
    assert historical["backendStatus"] == "closed"
    assert historical["elapsedDays"] == 5
    assert historical["ageStoppedAt"].startswith("2026-10-28")


def test_definitive_request_rejection_stops_the_counter(
    client, aged_request, session_factory,
):
    scenario = aged_request
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(scenario["request_id"]))
        request.status = ReimbursementRequestStatus.under_accounting_review
        request.reported_total = 0
        db.get(Expense, UUID(scenario["expense_id"])).status = ExpenseStatus.removed
        db.commit()
    rejected = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/transition/me",
        headers=scenario["headers"], json={"target_status": "rejected", "note": "Sin gastos pagables"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["rejected_at"].startswith("2026-10-28")
    Clock.current = datetime(2026, 11, 5, 18, tzinfo=UTC)
    assert _queue(client, scenario) == []
    item = _queue(client, scenario, historical=True)[0]
    assert item["elapsedDays"] == 5
    assert item["ageStoppedAt"].startswith("2026-10-28")


def test_daily_rollover_uses_mexico_date_and_missing_legacy_dates_stay_null(
    client, aged_request, session_factory,
):
    scenario = aged_request
    Clock.current = datetime(2026, 10, 28, 5, 59, tzinfo=UTC)
    assert _queue(client, scenario)[0]["elapsedDays"] == 4
    Clock.current = datetime(2026, 10, 28, 6, tzinfo=UTC)
    assert _queue(client, scenario)[0]["elapsedDays"] == 5
    with session_factory() as db:
        db.get(ReimbursementRequest, UUID(scenario["request_id"])).first_submitted_at = None
        db.commit()
    item = _queue(client, scenario)[0]
    assert item["elapsedDays"] is None
    assert item["firstSubmittedAt"] is None


def test_each_request_has_its_own_count_with_one_shared_server_cutoff(
    client, aged_request, session_factory,
):
    scenario = aged_request
    created = client.post("/api/v1/reimbursement-requests/", json={
        "store_id": scenario["store_id"], "period_id": scenario["period_id"],
    })
    assert created.status_code == 201, created.text
    second_id = created.json()["id"]
    with session_factory() as db:
        other = db.get(ReimbursementRequest, UUID(second_id))
        other.status = ReimbursementRequestStatus.under_accounting_review
        other.first_submitted_at = datetime(2026, 10, 26, 18, tzinfo=UTC)
        db.commit()
    rows = _queue(client, scenario)
    counts = {row["backendId"]: row["elapsedDays"] for row in rows}
    assert counts == {scenario["request_id"]: 5, second_id: 2}
    assert len({row["ageCalculatedAt"] for row in rows}) == 1
