from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.store import StoreUserAssignment
from app.models.user import User, UserRole
from app.schemas.reimbursement_request import (
    ReimbursementRequestQueueItemRead,
    ReimbursementRequestRead,
)
from app.services.frontend_actions import available_actions_for_request
from app.services.reimbursement_validation import summarize_reimbursement_request

router = APIRouter()


ROLE_QUEUE_STATUSES: dict[UserRole, set[ReimbursementRequestStatus]] = {
    UserRole.store: {
        ReimbursementRequestStatus.draft,
        ReimbursementRequestStatus.correction_required,
    },
    UserRole.authorizer: {
        ReimbursementRequestStatus.submitted,
        ReimbursementRequestStatus.authorization_review,
    },
    UserRole.accountant: {
        ReimbursementRequestStatus.submitted,
        ReimbursementRequestStatus.authorized,
        ReimbursementRequestStatus.under_accounting_review,
    },
    UserRole.accounting_manager: {
        ReimbursementRequestStatus.accounting_reviewed,
        ReimbursementRequestStatus.accounting_manager_review,
    },
    UserRole.treasury: {
        ReimbursementRequestStatus.accounting_manager_approved,
        ReimbursementRequestStatus.treasury_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
        ReimbursementRequestStatus.paid,
    },
    UserRole.director: {ReimbursementRequestStatus.direction_review},
}


@router.get("/me", response_model=list[ReimbursementRequestQueueItemRead])
def list_my_work_queue(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ReimbursementRequestQueueItemRead]:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.store),
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        )
        .order_by(ReimbursementRequest.created_at.desc())
    )

    if current_user.role == UserRole.admin:
        return [
            _build_queue_item(request, current_user)
            for request in db.scalars(statement.limit(200))
        ]

    statuses = ROLE_QUEUE_STATUSES.get(current_user.role, set())
    if not statuses:
        return []

    statement = statement.where(ReimbursementRequest.status.in_(statuses))
    statement = _scope_to_assigned_stores(statement, current_user)
    requests = [
        request
        for request in db.scalars(statement.limit(200))
        if _request_is_visible_for_role(request, current_user.role)
    ]
    return [_build_queue_item(request, current_user) for request in requests]


def _scope_to_assigned_stores(
    statement: Select[tuple[ReimbursementRequest]],
    current_user: User,
) -> Select[tuple[ReimbursementRequest]]:
    if current_user.role in {UserRole.treasury, UserRole.director}:
        return statement

    return statement.where(
        ReimbursementRequest.store_id.in_(
            select(StoreUserAssignment.store_id).where(
                StoreUserAssignment.user_id == current_user.id,
                StoreUserAssignment.role == current_user.role,
                StoreUserAssignment.is_active.is_(True),
            )
        )
    )


def _request_is_visible_for_role(request: ReimbursementRequest, role: UserRole) -> bool:
    if request.status != ReimbursementRequestStatus.submitted:
        return True

    summary = summarize_reimbursement_request(request)
    has_pending_authorization = bool(summary.missing_authorization_expense_ids)
    if role == UserRole.authorizer:
        return has_pending_authorization
    if role == UserRole.accountant:
        return not has_pending_authorization
    return True


def _build_queue_item(
    request: ReimbursementRequest,
    current_user: User,
) -> ReimbursementRequestQueueItemRead:
    summary = summarize_reimbursement_request(request)
    return ReimbursementRequestQueueItemRead(
        **ReimbursementRequestRead.model_validate(request).model_dump(),
        store=request.store,
        period=request.period,
        calculated_total=summary.calculated_total,
        expense_count=summary.expense_count,
        available_actions=available_actions_for_request(
            request,
            actor=current_user,
            summary=summary,
        ),
    )
