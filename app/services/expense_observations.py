from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseStatus
from app.models.reimbursement_request import ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.services.authorization_areas import user_can_authorize_expense_area
from app.services.permissions import user_can_transition_store_request

OBSERVATION_ROLES_BY_STATUS: dict[ReimbursementRequestStatus, set[UserRole]] = {
    ReimbursementRequestStatus.submitted: {
        UserRole.authorizer,
        UserRole.accountant,
        UserRole.admin,
    },
    ReimbursementRequestStatus.authorization_review: {UserRole.authorizer, UserRole.admin},
    ReimbursementRequestStatus.authorized: {
        UserRole.authorizer,
        UserRole.accountant,
        UserRole.admin,
    },
    ReimbursementRequestStatus.under_accounting_review: {UserRole.accountant, UserRole.admin},
    ReimbursementRequestStatus.accounting_reviewed: {
        UserRole.accountant,
        UserRole.accounting_manager,
        UserRole.admin,
    },
    ReimbursementRequestStatus.accounting_approved: {
        UserRole.accountant,
        UserRole.accounting_manager,
        UserRole.treasury,
        UserRole.admin,
    },
    ReimbursementRequestStatus.accounting_manager_review: {
        UserRole.accounting_manager,
        UserRole.admin,
    },
    ReimbursementRequestStatus.accounting_manager_approved: {
        UserRole.accounting_manager,
        UserRole.treasury,
        UserRole.admin,
    },
    ReimbursementRequestStatus.treasury_review: {UserRole.treasury, UserRole.admin},
    ReimbursementRequestStatus.direction_review: {
        UserRole.treasury,
        UserRole.director,
        UserRole.admin,
    },
    ReimbursementRequestStatus.direction_approved: {
        UserRole.accounting_manager,
        UserRole.treasury,
        UserRole.director,
        UserRole.admin,
    },
    ReimbursementRequestStatus.approved_for_payment: {
        UserRole.accounting_manager,
        UserRole.treasury,
        UserRole.director,
        UserRole.admin,
    },
}
OBSERVATION_LOCKED_STATUSES = {ReimbursementRequestStatus.paid, ReimbursementRequestStatus.closed}
STORE_OBSERVATION_STATUSES = {
    ReimbursementRequestStatus.draft,
    ReimbursementRequestStatus.correction_required,
}


def observation_roles_for_status(
    request_status: ReimbursementRequestStatus,
    *,
    authenticated: bool,
) -> set[UserRole]:
    roles = OBSERVATION_ROLES_BY_STATUS.get(request_status, set())
    # Do not open the legacy actor-id route to store users.
    if authenticated and request_status in STORE_OBSERVATION_STATUSES:
        return roles | {UserRole.store}
    return roles


def can_add_expense_observation(db: Session, actor: User, expense: Expense) -> bool:
    request = expense.reimbursement_request
    if request is None or request.status in OBSERVATION_LOCKED_STATUSES:
        return False
    if actor.role not in observation_roles_for_status(request.status, authenticated=True):
        return False
    if (
        expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected}
        or expense.removed_at is not None
    ):
        return False
    return user_can_transition_store_request(db, actor, request.store_id) or (
        actor.role == UserRole.authorizer
        and user_can_authorize_expense_area(db, actor, expense, store_id=request.store_id)
    )
