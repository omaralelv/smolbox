from dataclasses import dataclass
from datetime import UTC, datetime

from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.schemas.reimbursement_request import ReimbursementValidationSummary


class WorkflowTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class TransitionRule:
    allowed_from: set[ReimbursementRequestStatus]
    allowed_roles: set[UserRole]


ALLOWED_TRANSITIONS: dict[ReimbursementRequestStatus, TransitionRule] = {
    ReimbursementRequestStatus.submitted: TransitionRule(
        allowed_from={
            ReimbursementRequestStatus.draft,
            ReimbursementRequestStatus.correction_required,
        },
        allowed_roles={UserRole.store, UserRole.admin},
    ),
    ReimbursementRequestStatus.under_accounting_review: TransitionRule(
        allowed_from={ReimbursementRequestStatus.submitted},
        allowed_roles={UserRole.accountant, UserRole.admin},
    ),
    ReimbursementRequestStatus.correction_required: TransitionRule(
        allowed_from={ReimbursementRequestStatus.under_accounting_review},
        allowed_roles={UserRole.accountant, UserRole.admin},
    ),
    ReimbursementRequestStatus.accounting_approved: TransitionRule(
        allowed_from={ReimbursementRequestStatus.under_accounting_review},
        allowed_roles={UserRole.accountant, UserRole.admin},
    ),
    ReimbursementRequestStatus.treasury_review: TransitionRule(
        allowed_from={ReimbursementRequestStatus.accounting_approved},
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.approved_for_payment: TransitionRule(
        allowed_from={ReimbursementRequestStatus.treasury_review},
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.paid: TransitionRule(
        allowed_from={ReimbursementRequestStatus.approved_for_payment},
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.closed: TransitionRule(
        allowed_from={ReimbursementRequestStatus.paid},
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.rejected: TransitionRule(
        allowed_from={
            ReimbursementRequestStatus.under_accounting_review,
            ReimbursementRequestStatus.treasury_review,
        },
        allowed_roles={UserRole.accountant, UserRole.treasury, UserRole.admin},
    ),
}


def transition_reimbursement_request(
    request: ReimbursementRequest,
    *,
    actor: User,
    target_status: ReimbursementRequestStatus,
    summary: ReimbursementValidationSummary,
) -> tuple[ReimbursementRequestStatus, ReimbursementRequestStatus]:
    if not actor.is_active:
        raise WorkflowTransitionError("Actor user is inactive")

    current_status = request.status
    if current_status == target_status:
        raise WorkflowTransitionError("Request is already in the target status")

    rule = ALLOWED_TRANSITIONS.get(target_status)
    if rule is None:
        raise WorkflowTransitionError(f"Transition to {target_status.value} is not supported")

    if current_status not in rule.allowed_from:
        raise WorkflowTransitionError(
            f"Cannot move request from {current_status.value} to {target_status.value}"
        )

    if actor.role not in rule.allowed_roles:
        raise WorkflowTransitionError(
            f"Role {actor.role.value} cannot move request to {target_status.value}"
        )

    if target_status == ReimbursementRequestStatus.submitted and not summary.ready_for_submission:
        raise WorkflowTransitionError("Request is not ready to be submitted")

    if (
        target_status == ReimbursementRequestStatus.accounting_approved
        and not summary.ready_for_accounting_approval
    ):
        raise WorkflowTransitionError("Request is not ready for accounting approval")

    request.status = target_status
    _stamp_transition(request, target_status)
    return current_status, target_status


def _stamp_transition(
    request: ReimbursementRequest,
    target_status: ReimbursementRequestStatus,
) -> None:
    now = datetime.now(UTC)
    if target_status == ReimbursementRequestStatus.submitted:
        request.submitted_at = now
    elif target_status in {
        ReimbursementRequestStatus.correction_required,
        ReimbursementRequestStatus.accounting_approved,
        ReimbursementRequestStatus.rejected,
    }:
        request.accounting_reviewed_at = now
    elif target_status == ReimbursementRequestStatus.treasury_review:
        request.treasury_reviewed_at = now
    elif target_status == ReimbursementRequestStatus.approved_for_payment:
        request.approved_for_payment_at = now
    elif target_status == ReimbursementRequestStatus.paid:
        request.paid_at = now
    elif target_status == ReimbursementRequestStatus.closed:
        request.closed_at = now
