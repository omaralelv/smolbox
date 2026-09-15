from app.models.reimbursement_request import (
    AccountingQueueStatus,
    ReimbursementRequest,
    ReimbursementRequestStatus,
)
from app.models.user import User, UserRole
from app.schemas.reimbursement_request import ReimbursementValidationSummary


def mark_accounting_request_taken_on_open(
    request: ReimbursementRequest,
    *,
    actor: User,
    summary: ReimbursementValidationSummary,
) -> bool:
    if actor.role not in {UserRole.accountant, UserRole.admin}:
        return False
    if request.accounting_queue_status != AccountingQueueStatus.single:
        return False
    if not _is_accounting_queue_request(request, summary):
        return False

    request.accounting_queue_status = AccountingQueueStatus.taken
    return True


def _is_accounting_queue_request(
    request: ReimbursementRequest,
    summary: ReimbursementValidationSummary,
) -> bool:
    if request.status == ReimbursementRequestStatus.submitted:
        return not summary.missing_authorization_expense_ids
    return request.status in {
        ReimbursementRequestStatus.authorized,
        ReimbursementRequestStatus.under_accounting_review,
    }
