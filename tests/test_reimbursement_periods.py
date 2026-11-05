from datetime import date
from types import SimpleNamespace

import pytest

from app.services.reimbursement_periods import (
    ExpenseOutsideReimbursementPeriod,
    obtener_contexto_periodo_reembolso,
    validate_expense_date_for_reimbursement,
)


class _FakeResult:
    def __init__(self, row):
        self.row = row

    def first(self):
        return self.row


class _FakeSession:
    def __init__(self, previous_request=None, latest_expense=None, cutoff=None):
        self.previous_request = previous_request
        self.latest_expense = latest_expense
        self.cutoff = cutoff

    def execute(self, _statement):
        if self.previous_request is None:
            return _FakeResult(None)
        return _FakeResult((self.previous_request, self.latest_expense))

    def scalar(self, _statement):
        return self.cutoff


def _previous_request(*, starts_on: date, ends_on: date):
    return SimpleNamespace(
        id="previous-request-id",
        reimbursement_starts_on=starts_on,
        reimbursement_ends_on=ends_on,
        previous_reimbursement_request_id=None,
        previous_reimbursement_ends_on=date(2026, 7, 31),
        reported_total=None,
    )


def test_current_start_uses_actual_latest_previous_expense() -> None:
    previous_request = _previous_request(
        starts_on=date(2026, 8, 20),
        ends_on=date(2026, 9, 1),
    )

    context = obtener_contexto_periodo_reembolso(
        db=_FakeSession(
            previous_request,
            latest_expense=date(2026, 8, 30),
        ),
        store_id="store-id",
    )

    assert context.current_starts_on == date(2026, 8, 31)
    assert context.previous_starts_on == date(2026, 8, 1)
    assert context.previous_ends_on == date(2026, 8, 30)
    assert previous_request.reimbursement_starts_on == date(2026, 8, 1)
    assert previous_request.reimbursement_ends_on == date(2026, 8, 30)


def test_current_start_is_always_the_day_after_previous_expense() -> None:
    previous_request = _previous_request(
        starts_on=date(2026, 8, 1),
        ends_on=date(2026, 8, 31),
    )

    context = obtener_contexto_periodo_reembolso(
        db=_FakeSession(
            previous_request,
            latest_expense=date(2026, 8, 31),
        ),
        store_id="store-id",
    )

    assert context.current_starts_on == date(2026, 9, 1)


def test_first_period_uses_opening_cutoff() -> None:
    cutoff = SimpleNamespace(
        starts_on=date(2026, 6, 1),
        ends_on=date(2026, 6, 30),
        reimbursed_amount=1250,
    )

    context = obtener_contexto_periodo_reembolso(
        db=_FakeSession(cutoff=cutoff),
        store_id="store-id",
    )

    assert context.current_starts_on == date(2026, 7, 1)
    assert context.previous_starts_on == date(2026, 6, 1)
    assert context.previous_ends_on == date(2026, 6, 30)
    assert context.source == "opening_cutoff"


def test_expense_on_previous_end_date_is_accepted() -> None:
    validate_expense_date_for_reimbursement(
        date(2026, 8, 31),
        previous_ends_on=date(2026, 8, 31),
    )


def test_expense_before_previous_end_date_is_rejected() -> None:
    with pytest.raises(ExpenseOutsideReimbursementPeriod):
        validate_expense_date_for_reimbursement(
            date(2026, 8, 30),
            previous_ends_on=date(2026, 8, 31),
        )
