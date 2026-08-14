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
    ReimbursementRequestStatus.authorization_review: TransitionRule(
        allowed_from={ReimbursementRequestStatus.submitted},
        allowed_roles={UserRole.authorizer, UserRole.admin},
    ),
    ReimbursementRequestStatus.authorized: TransitionRule(
        allowed_from={ReimbursementRequestStatus.authorization_review},
        allowed_roles={UserRole.authorizer, UserRole.admin},
    ),
    ReimbursementRequestStatus.under_accounting_review: TransitionRule(
        allowed_from={ReimbursementRequestStatus.authorized},
        allowed_roles={UserRole.accountant, UserRole.admin},
    ),
    ReimbursementRequestStatus.correction_required: TransitionRule(
        allowed_from={
            ReimbursementRequestStatus.authorization_review,
            ReimbursementRequestStatus.under_accounting_review,
            ReimbursementRequestStatus.accounting_manager_review,
            ReimbursementRequestStatus.treasury_review,
            ReimbursementRequestStatus.direction_review,
        },
        allowed_roles={
            UserRole.authorizer,
            UserRole.accountant,
            UserRole.accounting_manager,
            UserRole.treasury,
            UserRole.director,
            UserRole.admin,
        },
    ),
    ReimbursementRequestStatus.accounting_reviewed: TransitionRule(
        allowed_from={ReimbursementRequestStatus.under_accounting_review},
        allowed_roles={UserRole.accountant, UserRole.admin},
    ),
    ReimbursementRequestStatus.accounting_approved: TransitionRule(
        allowed_from={ReimbursementRequestStatus.under_accounting_review},
        allowed_roles={UserRole.accountant, UserRole.admin},
    ),
    ReimbursementRequestStatus.accounting_manager_review: TransitionRule(
        allowed_from={ReimbursementRequestStatus.accounting_reviewed},
        allowed_roles={UserRole.accounting_manager, UserRole.admin},
    ),
    ReimbursementRequestStatus.accounting_manager_approved: TransitionRule(
        allowed_from={ReimbursementRequestStatus.accounting_manager_review},
        allowed_roles={UserRole.accounting_manager, UserRole.admin},
    ),
    ReimbursementRequestStatus.treasury_review: TransitionRule(
        allowed_from={
            ReimbursementRequestStatus.accounting_approved,
            ReimbursementRequestStatus.accounting_manager_approved,
        },
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.direction_review: TransitionRule(
        allowed_from={ReimbursementRequestStatus.treasury_review},
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.direction_approved: TransitionRule(
        allowed_from={ReimbursementRequestStatus.direction_review},
        allowed_roles={UserRole.director, UserRole.admin},
    ),
    ReimbursementRequestStatus.approved_for_payment: TransitionRule(
        allowed_from={ReimbursementRequestStatus.direction_approved},
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.closed: TransitionRule(
        allowed_from={ReimbursementRequestStatus.paid},
        allowed_roles={UserRole.treasury, UserRole.admin},
    ),
    ReimbursementRequestStatus.rejected: TransitionRule(
        allowed_from={
            ReimbursementRequestStatus.authorization_review,
            ReimbursementRequestStatus.under_accounting_review,
            ReimbursementRequestStatus.accounting_manager_review,
            ReimbursementRequestStatus.treasury_review,
            ReimbursementRequestStatus.direction_review,
        },
        allowed_roles={
            UserRole.authorizer,
            UserRole.accountant,
            UserRole.accounting_manager,
            UserRole.treasury,
            UserRole.director,
            UserRole.admin,
        },
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

    if target_status == ReimbursementRequestStatus.paid:
        raise WorkflowTransitionError("Requests can only be marked paid by recording a treasury payment")

    rule = ALLOWED_TRANSITIONS.get(target_status)
    if rule is None:
        raise WorkflowTransitionError(f"Transition to {target_status.value} is not supported")

    is_correction_return = (
        current_status == ReimbursementRequestStatus.submitted
        and request.correction_return_status == target_status
    )

    if current_status not in rule.allowed_from and not is_correction_return:
        raise WorkflowTransitionError(
            f"Cannot move request from {current_status.value} to {target_status.value}"
        )

    if actor.role not in rule.allowed_roles:
        raise WorkflowTransitionError(
            f"Role {actor.role.value} cannot move request to {target_status.value}"
        )

    if target_status in {
        ReimbursementRequestStatus.correction_required,
        ReimbursementRequestStatus.rejected,
    }:
        current_review_roles = _review_roles_for_status(current_status)
        if actor.role not in current_review_roles and actor.role != UserRole.admin:
            raise WorkflowTransitionError(
                f"Role {actor.role.value} cannot review request in {current_status.value}"
            )

    if (
        target_status == ReimbursementRequestStatus.rejected
        and current_status == ReimbursementRequestStatus.authorization_review
        and not _has_no_payable_expenses(summary)
    ):
        raise WorkflowTransitionError(
            "Authorization can reject the full request only when no payable expenses remain"
        )

    if target_status == ReimbursementRequestStatus.submitted and not summary.ready_for_submission:
        raise WorkflowTransitionError("Request is not ready to be submitted")

    if (
        target_status == ReimbursementRequestStatus.authorized
        and not summary.ready_for_authorization_approval
    ):
        raise WorkflowTransitionError("Request still has expenses pending authorization")

    if (
        target_status
        in {
            ReimbursementRequestStatus.accounting_reviewed,
            ReimbursementRequestStatus.accounting_approved,
        }
        and not summary.ready_for_accounting_approval
    ):
        raise WorkflowTransitionError("Request is not ready for accounting review completion")

    if (
        target_status == ReimbursementRequestStatus.accounting_manager_review
        and request.sap_policy_generated_at is None
    ):
        raise WorkflowTransitionError(
            "SAP policy placeholder must be prepared before manager review"
        )

    request.status = target_status
    _stamp_transition(request, target_status, from_status=current_status)
    return current_status, target_status


def _stamp_transition(
    request: ReimbursementRequest,
    target_status: ReimbursementRequestStatus,
    *,
    from_status: ReimbursementRequestStatus,
) -> None:
    now = datetime.now(UTC)
    if target_status == ReimbursementRequestStatus.submitted:
        request.submitted_at = now
    elif target_status == ReimbursementRequestStatus.authorized:
        request.authorization_reviewed_at = now
    elif target_status == ReimbursementRequestStatus.rejected:
        if from_status == ReimbursementRequestStatus.authorization_review:
            request.authorization_reviewed_at = now
        elif from_status == ReimbursementRequestStatus.accounting_manager_review:
            request.accounting_manager_reviewed_at = now
        elif from_status == ReimbursementRequestStatus.treasury_review:
            request.treasury_reviewed_at = now
        elif from_status == ReimbursementRequestStatus.direction_review:
            request.direction_reviewed_at = now
        else:
            request.accounting_reviewed_at = now
    elif target_status in {
        ReimbursementRequestStatus.accounting_reviewed,
        ReimbursementRequestStatus.correction_required,
        ReimbursementRequestStatus.accounting_approved,
    }:
        request.accounting_reviewed_at = now
    elif target_status == ReimbursementRequestStatus.accounting_manager_approved:
        request.accounting_manager_reviewed_at = now
    elif target_status == ReimbursementRequestStatus.treasury_review:
        request.treasury_reviewed_at = now
    elif target_status == ReimbursementRequestStatus.direction_review:
        request.direction_reviewed_at = now
    elif target_status == ReimbursementRequestStatus.direction_approved:
        request.direction_approved_at = now
    elif target_status == ReimbursementRequestStatus.approved_for_payment:
        request.approved_for_payment_at = now
    elif target_status == ReimbursementRequestStatus.paid:
        request.paid_at = now
    elif target_status == ReimbursementRequestStatus.closed:
        request.closed_at = now


def _review_roles_for_status(status: ReimbursementRequestStatus) -> set[UserRole]:
    if status == ReimbursementRequestStatus.authorization_review:
        return {UserRole.authorizer}
    if status == ReimbursementRequestStatus.under_accounting_review:
        return {UserRole.accountant}
    if status == ReimbursementRequestStatus.accounting_manager_review:
        return {UserRole.accounting_manager}
    if status == ReimbursementRequestStatus.treasury_review:
        return {UserRole.treasury}
    if status == ReimbursementRequestStatus.direction_review:
        return {UserRole.director}
    return set()


def _has_no_payable_expenses(summary: ReimbursementValidationSummary) -> bool:
    return summary.expense_count == 0 and (
        bool(summary.rejected_expense_ids) or bool(summary.removed_expense_ids)
    )
