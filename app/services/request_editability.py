from app.models.reimbursement_request import (
    ReimbursementRequest,
    ReimbursementRequestStatus,
)

EDITABLE_REQUEST_STATUSES = {
    ReimbursementRequestStatus.draft,
    ReimbursementRequestStatus.correction_required,
}


def is_request_editable(reimbursement_request: ReimbursementRequest) -> bool:
    return reimbursement_request.status in EDITABLE_REQUEST_STATUSES
