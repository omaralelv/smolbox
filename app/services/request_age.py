from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus

MEXICO_CITY_TZ = ZoneInfo("America/Mexico_City")
TERMINAL_STATUSES = {
    ReimbursementRequestStatus.paid,
    ReimbursementRequestStatus.closed,
    ReimbursementRequestStatus.rejected,
}


@dataclass(frozen=True)
class RequestAge:
    first_submitted_at: datetime | None
    stopped_at: datetime | None
    calculated_at: datetime
    elapsed_days: int | None


def request_age(request: ReimbursementRequest, *, now: datetime | None = None) -> RequestAge:
    calculated_at = _utc(now or datetime.now(UTC))
    started_at = _utc(request.first_submitted_at)
    if request.status == ReimbursementRequestStatus.rejected:
        stopped_at = _utc(request.rejected_at)
    elif request.status in {ReimbursementRequestStatus.paid, ReimbursementRequestStatus.closed}:
        stopped_at = _utc(request.paid_at)
    else:
        stopped_at = None

    # A terminal request with no proven payment/rejection date must not keep aging.
    end = stopped_at if request.status in TERMINAL_STATUSES else calculated_at
    days = None
    if (request.status != ReimbursementRequestStatus.draft and started_at is not None
            and end is not None and started_at <= end <= calculated_at):
        days = (end.astimezone(MEXICO_CITY_TZ).date()
                - started_at.astimezone(MEXICO_CITY_TZ).date()).days
    return RequestAge(started_at, stopped_at, calculated_at, days)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC)
