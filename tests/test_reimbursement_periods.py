from datetime import date
from types import SimpleNamespace

from app.services.reimbursement_periods import obtener_contexto_periodo_reembolso


class _FakeSession:
    def __init__(self, previous_request):
        self.previous_request = previous_request

    def scalar(self, _statement):
        return self.previous_request


def _previous_request(*, starts_on: date, ends_on: date):
    return SimpleNamespace(
        id="previous-request-id",
        reimbursement_starts_on=starts_on,
        reimbursement_ends_on=ends_on,
        reported_total=None,
    )


def test_same_day_request_reuses_previous_coverage_dates() -> None:
    previous_request = _previous_request(
        starts_on=date(2026, 8, 1),
        ends_on=date(2026, 8, 31),
    )

    context = obtener_contexto_periodo_reembolso(
        db=_FakeSession(previous_request),
        store_id="store-id",
        fecha_fin_actual=date(2026, 8, 31),
    )

    assert context.current_starts_on == date(2026, 8, 1)
    assert context.previous_starts_on == date(2026, 8, 1)
    assert context.previous_ends_on == date(2026, 8, 31)


def test_different_day_request_starts_after_previous_coverage() -> None:
    previous_request = _previous_request(
        starts_on=date(2026, 8, 1),
        ends_on=date(2026, 8, 31),
    )

    context = obtener_contexto_periodo_reembolso(
        db=_FakeSession(previous_request),
        store_id="store-id",
        fecha_fin_actual=date(2026, 9, 30),
    )

    assert context.current_starts_on == date(2026, 9, 1)
