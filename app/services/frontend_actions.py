from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.schemas.reimbursement_request import ReimbursementValidationSummary


def available_actions_for_request(
    request: ReimbursementRequest,
    *,
    actor: User,
    summary: ReimbursementValidationSummary,
) -> list[str]:
    role = actor.role
    status = request.status
    actions: list[str] = []

    if status in {
        ReimbursementRequestStatus.draft,
        ReimbursementRequestStatus.correction_required,
    } and role in {UserRole.store, UserRole.admin}:
        actions.extend(
            [
                "edit_request",
                "add_expense",
                "upload_request_attachment",
                "submit_request",
            ]
        )

    if status == ReimbursementRequestStatus.submitted:
        if summary.missing_authorization_expense_ids and role in {
            UserRole.authorizer,
            UserRole.admin,
        }:
            actions.append("start_authorization_review")
        if not summary.missing_authorization_expense_ids and role in {
            UserRole.accountant,
            UserRole.admin,
        }:
            actions.append("start_accounting_review")

    if status == ReimbursementRequestStatus.authorization_review and role in {
        UserRole.authorizer,
        UserRole.admin,
    }:
        actions.extend(
            [
                "authorize_expense",
                "reject_expense",
                "remove_authorization_expense",
                "approve_authorization",
                "reject_request",
            ]
        )

    if status == ReimbursementRequestStatus.authorized and role in {
        UserRole.accountant,
        UserRole.admin,
    }:
        actions.append("start_accounting_review")

    if status == ReimbursementRequestStatus.under_accounting_review and role in {
        UserRole.accountant,
        UserRole.admin,
    }:
        actions.extend(
            [
                "edit_expense",
                "observe_expense",
                "remove_expense",
                "prepare_sap_policy",
                "mark_accounting_reviewed",
                "reject_request",
            ]
        )

    if status == ReimbursementRequestStatus.accounting_reviewed and role in {
        UserRole.accounting_manager,
        UserRole.admin,
    }:
        actions.append("start_accounting_manager_review")

    if status == ReimbursementRequestStatus.accounting_manager_review and role in {
        UserRole.accounting_manager,
        UserRole.admin,
    }:
        actions.extend(["approve_accounting_manager", "return_to_accounting", "reject_request"])

    if status == ReimbursementRequestStatus.accounting_manager_approved and role in {
        UserRole.treasury,
        UserRole.admin,
    }:
        actions.append("start_treasury_review")

    if status == ReimbursementRequestStatus.treasury_review and role in {
        UserRole.treasury,
        UserRole.admin,
    }:
        actions.extend(["send_to_direction", "return_to_manager", "reject_request"])

    if status == ReimbursementRequestStatus.direction_review and role in {
        UserRole.director,
        UserRole.admin,
    }:
        actions.extend(["approve_direction", "return_to_treasury", "reject_request"])

    if status == ReimbursementRequestStatus.direction_approved and role in {
        UserRole.treasury,
        UserRole.admin,
    }:
        actions.append("mark_approved_for_payment")

    if status == ReimbursementRequestStatus.approved_for_payment and role in {
        UserRole.treasury,
        UserRole.admin,
    }:
        actions.append("record_payment")

    if status == ReimbursementRequestStatus.paid and role in {UserRole.treasury, UserRole.admin}:
        actions.append("close_request")

    return actions
