from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_workflow import _summary

from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.services.request_age import request_age
from app.services.workflow import transition_reimbursement_request


def _date(value):
    return datetime.fromisoformat(value)


@pytest.mark.parametrize("status", [
    status for status in ReimbursementRequestStatus
    if status not in {
        ReimbursementRequestStatus.draft, ReimbursementRequestStatus.paid,
        ReimbursementRequestStatus.closed, ReimbursementRequestStatus.rejected,
    }
])
def test_age_continues_across_all_active_stages_and_returns(status):
    request = ReimbursementRequest(
        status=status, first_submitted_at=_date("2026-10-23T18:00:00Z"),
        submitted_at=_date("2026-10-27T18:00:00Z"),
    )
    age = request_age(request, now=_date("2026-10-28T18:00:00Z"))
    assert age.elapsed_days == 5
    assert age.stopped_at is None
    assert request.submitted_at == _date("2026-10-27T18:00:00Z")


@pytest.mark.parametrize("start,end,days", [
    ("2026-10-28T06:00:00Z", "2026-10-28T23:00:00Z", 0),
    ("2026-10-28T05:59:00Z", "2026-10-28T06:00:00Z", 1),
    ("2026-10-28T04:00:00Z", "2026-10-28T05:59:00Z", 0),
    ("2026-10-23T18:00:00Z", "2026-10-26T18:00:00Z", 3),
    ("2026-10-31T18:00:00Z", "2026-11-02T18:00:00Z", 2),
    ("2024-02-28T18:00:00Z", "2024-03-01T18:00:00Z", 2),
    ("2021-04-04T06:00:00Z", "2021-04-05T05:00:00Z", 1),
])
def test_age_uses_mexico_calendar_dates_not_completed_24_hour_periods(start, end, days):
    request = ReimbursementRequest(status="submitted", first_submitted_at=_date(start))
    assert request_age(request, now=_date(end)).elapsed_days == days


@pytest.mark.parametrize("status", ["paid", "closed", "rejected"])
def test_age_stops_on_payment_or_rejection_and_not_on_a_later_closure(status):
    request = ReimbursementRequest(
        status=status, first_submitted_at=_date("2026-10-23T18:00:00Z"),
        paid_at=_date("2026-10-26T18:00:00Z") if status != "rejected" else None,
        rejected_at=_date("2026-10-26T18:00:00Z") if status == "rejected" else None,
        closed_at=_date("2026-10-29T18:00:00Z"),
    )
    for now in ("2026-10-30T18:00:00Z", "2026-12-31T18:00:00Z"):
        age = request_age(request, now=_date(now))
        assert age.elapsed_days == 3
        assert age.stopped_at == _date("2026-10-26T18:00:00Z")


@pytest.mark.parametrize("status", ["submitted", "paid", "closed", "rejected"])
def test_missing_dates_are_unknown_instead_of_invented_from_creation_or_last_submission(status):
    request = ReimbursementRequest(
        status=status, created_at=_date("2026-10-01T12:00:00Z"),
        submitted_at=_date("2026-10-23T12:00:00Z"),
    )
    assert request_age(request).elapsed_days is None
    request.first_submitted_at = _date("2026-10-23T12:00:00Z")
    if status != "submitted":
        assert request_age(request).elapsed_days is None


@pytest.mark.parametrize("start,end", [
    ("2026-10-30T12:00:00Z", None),
    ("2026-10-28T12:00:00Z", "2026-10-27T12:00:00Z"),
    ("2026-10-23T12:00:00Z", "2026-10-30T12:00:00Z"),
])
def test_inconsistent_or_future_dates_do_not_show_negative_or_invented_durations(start, end):
    request = ReimbursementRequest(
        status="paid" if end else "submitted", first_submitted_at=_date(start),
        paid_at=_date(end) if end else None,
    )
    assert request_age(request, now=_date("2026-10-28T18:00:00Z")).elapsed_days is None


def test_naive_database_timestamps_are_interpreted_as_utc_and_drafts_do_not_age():
    request = ReimbursementRequest(
        status="submitted", first_submitted_at=_date("2026-10-23T18:00:00Z").replace(tzinfo=None),
    )
    age = request_age(request, now=_date("2026-10-28T18:00:00Z").replace(tzinfo=None))
    assert age.elapsed_days == 5
    assert age.first_submitted_at.tzinfo == UTC
    request.status = ReimbursementRequestStatus.draft
    assert request_age(request).elapsed_days is None


def test_first_submission_is_persisted_once_and_corrections_do_not_reset_it():
    request = ReimbursementRequest(status=ReimbursementRequestStatus.draft)
    store = User(id=uuid4(), role=UserRole.store, is_active=True)
    transition_reimbursement_request(
        request, actor=store, target_status=ReimbursementRequestStatus.submitted, summary=_summary(),
    )
    assert request.first_submitted_at == request.submitted_at
    original = _date("2026-10-23T18:00:00Z")
    request.first_submitted_at = original
    request.status = ReimbursementRequestStatus.correction_required
    transition_reimbursement_request(
        request, actor=store, target_status=ReimbursementRequestStatus.submitted, summary=_summary(),
    )
    assert request.first_submitted_at == original
    assert request.submitted_at > original


def test_legacy_correction_without_first_submission_evidence_stays_unknown():
    request = ReimbursementRequest(
        status=ReimbursementRequestStatus.correction_required,
        submitted_at=_date("2026-10-23T18:00:00Z"),
    )
    transition_reimbursement_request(
        request, actor=User(role=UserRole.store, is_active=True),
        target_status=ReimbursementRequestStatus.submitted, summary=_summary(),
    )
    assert request.first_submitted_at is None
    assert request_age(request).elapsed_days is None


def test_definitive_rejection_records_its_own_timestamp():
    from test_workflow import _no_payable_summary

    request = ReimbursementRequest(
        status=ReimbursementRequestStatus.under_accounting_review,
        first_submitted_at=_date("2026-10-23T18:00:00Z"),
    )
    transition_reimbursement_request(
        request, actor=User(role=UserRole.admin, is_active=True),
        target_status=ReimbursementRequestStatus.rejected, summary=_no_payable_summary(),
    )
    assert request.rejected_at is not None
    assert request.rejected_at == request.accounting_reviewed_at
    age = request_age(request)
    assert age.stopped_at == request.rejected_at
