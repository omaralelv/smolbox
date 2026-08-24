from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditActorType, AuditLog
from app.models.cfdi_validation import CfdiValidation
from app.models.expense import Expense, ExpenseStatus
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.schemas.expense import (
    AuthenticatedExpenseAuthorization,
    AuthenticatedExpenseObservation,
    AuthenticatedExpenseRejection,
    AuthenticatedExpenseRemoval,
    AuthenticatedExpenseReviewUpdate,
    ExpenseAuthorization,
    ExpenseCreate,
    ExpenseObservation,
    ExpenseRead,
    ExpenseRejection,
    ExpenseRemoval,
    ExpenseReviewUpdate,
    ExpenseUpdate,
)
from app.services.permissions import user_can_transition_store_request
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.request_editability import is_request_editable
from app.services.workflow import transition_reimbursement_request

router = APIRouter()

OBSERVATION_ROLES_BY_STATUS: dict[ReimbursementRequestStatus, set[UserRole]] = {
    ReimbursementRequestStatus.authorization_review: {UserRole.authorizer, UserRole.admin},
    ReimbursementRequestStatus.under_accounting_review: {UserRole.accountant, UserRole.admin},
    ReimbursementRequestStatus.accounting_manager_review: {
        UserRole.accounting_manager,
        UserRole.admin,
    },
    ReimbursementRequestStatus.treasury_review: {UserRole.treasury, UserRole.admin},
    ReimbursementRequestStatus.direction_review: {UserRole.director, UserRole.admin},
}

REVIEW_EDIT_ROLES_BY_STATUS: dict[ReimbursementRequestStatus, set[UserRole]] = {
    ReimbursementRequestStatus.under_accounting_review: {UserRole.accountant, UserRole.admin},
    ReimbursementRequestStatus.accounting_manager_review: {
        UserRole.accounting_manager,
        UserRole.admin,
    },
}

REMOVAL_ROLES_BY_STATUS: dict[ReimbursementRequestStatus, set[UserRole]] = {
    ReimbursementRequestStatus.authorization_review: {UserRole.authorizer, UserRole.admin},
    **REVIEW_EDIT_ROLES_BY_STATUS,
}


@router.post("/", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(
    expense_in: ExpenseCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense_data = expense_in.model_dump()
    request_id = expense_data.get("reimbursement_request_id")

    if request_id is not None:
        reimbursement_request = db.get(ReimbursementRequest, request_id)
        if reimbursement_request is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reimbursement request not found",
            )
        _ensure_request_editable(
            reimbursement_request,
            message="Expenses can only be created while the request is draft or in correction.",
        )
        if expense_data.get("period_id") is None:
            expense_data["period_id"] = reimbursement_request.period_id
        elif expense_data["period_id"] != reimbursement_request.period_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expense period must match the reimbursement request period",
            )

    period = db.get(Period, expense_data["period_id"])
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERIOD_CLOSED", "message": "The reimbursement period is closed"},
        )
    if not period.starts_on <= expense_in.spent_on <= period.ends_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "EXPENSE_OUTSIDE_PERIOD",
                "message": "The expense date is outside the reimbursement period",
            },
        )

    expense = Expense(**expense_data)
    db.add(expense)
    db.flush()
    if expense.reimbursement_request_id is not None:
        db.add(
            AuditLog(
                reimbursement_request_id=expense.reimbursement_request_id,
                expense_id=expense.id,
                actor_type=AuditActorType.system,
                action="expense_created",
                message=f"Expense created for {expense.merchant}.",
                event_payload={
                    "amount": str(expense.amount),
                    "currency": expense.currency,
                    "category": expense.category,
                    "spent_on": expense.spent_on.isoformat(),
                },
            )
        )
    db.commit()
    db.refresh(expense)
    return expense


@router.get("/", response_model=list[ExpenseRead])
def list_expenses(
    db: Annotated[Session, Depends(get_db)],
    period_id: UUID | None = None,
    reimbursement_request_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Expense]:
    statement = select(Expense).order_by(Expense.created_at.desc()).limit(limit).offset(offset)
    if period_id is not None:
        statement = statement.where(Expense.period_id == period_id)
    if reimbursement_request_id is not None:
        statement = statement.where(Expense.reimbursement_request_id == reimbursement_request_id)
    return list(db.scalars(statement))


@router.get("/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: UUID, db: Annotated[Session, Depends(get_db)]) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


@router.post("/{expense_id}/authorize", response_model=ExpenseRead)
def authorize_expense(
    expense_id: UUID,
    authorization_in: ExpenseAuthorization,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    actor = _get_actor_or_404(authorization_in.actor_user_id, db)
    return _authorize_expense_with_actor(
        expense,
        actor=actor,
        note=authorization_in.note,
        require_store_assignment=False,
        db=db,
    )


@router.post("/{expense_id}/authorize/me", response_model=ExpenseRead)
def authorize_expense_as_current_user(
    expense_id: UUID,
    authorization_in: AuthenticatedExpenseAuthorization,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    return _authorize_expense_with_actor(
        expense,
        actor=current_user,
        note=authorization_in.note,
        require_store_assignment=True,
        db=db,
    )


@router.post("/{expense_id}/reject", response_model=ExpenseRead)
def reject_expense_authorization(
    expense_id: UUID,
    rejection_in: ExpenseRejection,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    actor = _get_actor_or_404(rejection_in.actor_user_id, db)
    return _reject_expense_with_actor(
        expense,
        actor=actor,
        reason=rejection_in.reason,
        adjust_reported_total=rejection_in.adjust_reported_total,
        require_store_assignment=False,
        db=db,
    )


@router.post("/{expense_id}/reject/me", response_model=ExpenseRead)
def reject_expense_authorization_as_current_user(
    expense_id: UUID,
    rejection_in: AuthenticatedExpenseRejection,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    return _reject_expense_with_actor(
        expense,
        actor=current_user,
        reason=rejection_in.reason,
        adjust_reported_total=rejection_in.adjust_reported_total,
        require_store_assignment=True,
        db=db,
    )


@router.post("/{expense_id}/observation", response_model=ExpenseRead)
def add_expense_observation(
    expense_id: UUID,
    observation_in: ExpenseObservation,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    actor = _get_actor_or_404(observation_in.actor_user_id, db)
    return _add_observation_with_actor(
        expense,
        actor=actor,
        note=observation_in.note,
        require_store_assignment=False,
        db=db,
    )


@router.post("/{expense_id}/observation/me", response_model=ExpenseRead)
def add_expense_observation_as_current_user(
    expense_id: UUID,
    observation_in: AuthenticatedExpenseObservation,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    return _add_observation_with_actor(
        expense,
        actor=current_user,
        note=observation_in.note,
        require_store_assignment=True,
        db=db,
    )


@router.patch("/{expense_id}/review", response_model=ExpenseRead)
def review_update_expense(
    expense_id: UUID,
    expense_in: ExpenseReviewUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    actor = _get_actor_or_404(expense_in.actor_user_id, db)
    updates = expense_in.model_dump(exclude_unset=True)
    updates.pop("actor_user_id", None)
    note = updates.pop("note", None)
    return _review_update_expense_with_actor(
        expense,
        actor=actor,
        updates=updates,
        note=note,
        require_store_assignment=False,
        db=db,
    )


@router.patch("/{expense_id}/review/me", response_model=ExpenseRead)
def review_update_expense_as_current_user(
    expense_id: UUID,
    expense_in: AuthenticatedExpenseReviewUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    updates = expense_in.model_dump(exclude_unset=True)
    note = updates.pop("note", None)
    return _review_update_expense_with_actor(
        expense,
        actor=current_user,
        updates=updates,
        note=note,
        require_store_assignment=True,
        db=db,
    )


@router.post("/{expense_id}/remove", response_model=ExpenseRead)
def remove_expense_from_review(
    expense_id: UUID,
    removal_in: ExpenseRemoval,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    actor = _get_actor_or_404(removal_in.actor_user_id, db)
    return _remove_expense_with_actor(
        expense,
        actor=actor,
        reason=removal_in.reason,
        adjust_reported_total=removal_in.adjust_reported_total,
        require_store_assignment=False,
        db=db,
    )


@router.post("/{expense_id}/remove/me", response_model=ExpenseRead)
def remove_expense_from_review_as_current_user(
    expense_id: UUID,
    removal_in: AuthenticatedExpenseRemoval,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    return _remove_expense_with_actor(
        expense,
        actor=current_user,
        reason=removal_in.reason,
        adjust_reported_total=removal_in.adjust_reported_total,
        require_store_assignment=True,
        db=db,
    )


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: UUID,
    expense_in: ExpenseUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    if expense.reimbursement_request is not None:
        _ensure_request_editable(
            expense.reimbursement_request,
            message="Expenses can only be edited while the request is draft or in correction.",
        )

    updates = expense_in.model_dump(exclude_unset=True)
    _apply_expense_updates(expense, updates, db)
    changed_fields = sorted(updates)
    if expense.reimbursement_request_id is not None and changed_fields:
        db.add(
            AuditLog(
                reimbursement_request_id=expense.reimbursement_request_id,
                expense_id=expense.id,
                actor_type=AuditActorType.system,
                action="expense_updated",
                message="Expense updated.",
                event_payload={"changed_fields": changed_fields},
            )
        )

    db.commit()
    db.refresh(expense)
    return expense


def _authorize_expense_with_actor(
    expense: Expense,
    *,
    actor: User,
    note: str | None,
    require_store_assignment: bool,
    db: Session,
) -> Expense:
    reimbursement_request = _attached_request_or_conflict(expense)
    if reimbursement_request.status != ReimbursementRequestStatus.authorization_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_IN_AUTHORIZATION_REVIEW",
                "message": "Expenses can only be authorized during authorization review.",
            },
        )
    _ensure_actor_can(actor, {UserRole.authorizer, UserRole.admin})
    _ensure_store_assignment_if_required(db, actor, reimbursement_request, require_store_assignment)
    _ensure_expense_not_excluded(expense)

    expense.requires_authorization = True
    expense.authorized_at = datetime.now(UTC)
    expense.authorized_by_user_id = actor.id
    expense.authorization_note = note
    expense.status = ExpenseStatus.approved
    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_authorized",
            message=note,
            event_payload={
                "actor_role": actor.role.value,
                "authenticated": require_store_assignment,
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


def _reject_expense_with_actor(
    expense: Expense,
    *,
    actor: User,
    reason: str,
    adjust_reported_total: bool,
    require_store_assignment: bool,
    db: Session,
) -> Expense:
    reimbursement_request = _attached_request_or_conflict(expense)
    if reimbursement_request.status != ReimbursementRequestStatus.authorization_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_IN_AUTHORIZATION_REVIEW",
                "message": "Expenses can only be rejected during authorization review.",
            },
        )
    _ensure_actor_can(actor, {UserRole.authorizer, UserRole.admin})
    _ensure_store_assignment_if_required(db, actor, reimbursement_request, require_store_assignment)
    _ensure_expense_not_excluded(expense)
    if expense.authorized_at is not None or expense.status == ExpenseStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXPENSE_ALREADY_AUTHORIZED",
                "message": "Authorized expenses cannot be rejected.",
            },
        )

    expense.requires_authorization = True
    expense.status = ExpenseStatus.rejected
    expense.authorization_note = reason
    if adjust_reported_total:
        reimbursement_request.reported_total = _active_expense_total(reimbursement_request)

    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_authorization_rejected",
            message=reason,
            event_payload={
                "actor_role": actor.role.value,
                "reported_total": str(reimbursement_request.reported_total),
                "authenticated": require_store_assignment,
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


def _add_observation_with_actor(
    expense: Expense,
    *,
    actor: User,
    note: str,
    require_store_assignment: bool,
    db: Session,
) -> Expense:
    reimbursement_request = _attached_request_or_conflict(expense)
    _ensure_actor_can(actor, OBSERVATION_ROLES_BY_STATUS.get(reimbursement_request.status, set()))
    _ensure_store_assignment_if_required(db, actor, reimbursement_request, require_store_assignment)
    _ensure_expense_not_excluded(expense)

    expense.review_note = note
    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_observation_added",
            message=note,
            event_payload={
                "actor_role": actor.role.value,
                "request_status": reimbursement_request.status.value,
                "authenticated": require_store_assignment,
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


def _review_update_expense_with_actor(
    expense: Expense,
    *,
    actor: User,
    updates: dict[str, object],
    note: str | None,
    require_store_assignment: bool,
    db: Session,
) -> Expense:
    reimbursement_request = _attached_request_or_conflict(expense)
    _ensure_actor_can(actor, REVIEW_EDIT_ROLES_BY_STATUS.get(reimbursement_request.status, set()))
    _ensure_store_assignment_if_required(db, actor, reimbursement_request, require_store_assignment)
    _ensure_expense_not_excluded(expense)

    _apply_expense_updates(expense, updates, db)
    if note:
        expense.review_note = note
    if {"amount", "currency", "supplier_tax_id", "requires_authorization"} & set(updates):
        reimbursement_request.reported_total = _active_expense_total(reimbursement_request)

    changed_fields = sorted(updates)
    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_review_updated",
            message=note,
            event_payload={
                "actor_role": actor.role.value,
                "request_status": reimbursement_request.status.value,
                "changed_fields": changed_fields,
                "reported_total": str(reimbursement_request.reported_total),
                "authenticated": require_store_assignment,
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


def _remove_expense_with_actor(
    expense: Expense,
    *,
    actor: User,
    reason: str,
    adjust_reported_total: bool,
    require_store_assignment: bool,
    db: Session,
) -> Expense:
    reimbursement_request = _attached_request_or_conflict(expense)
    _ensure_actor_can(actor, REMOVAL_ROLES_BY_STATUS.get(reimbursement_request.status, set()))
    _ensure_store_assignment_if_required(db, actor, reimbursement_request, require_store_assignment)
    _ensure_expense_not_excluded(expense)
    if (
        reimbursement_request.status == ReimbursementRequestStatus.authorization_review
        and not expense.requires_authorization
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXPENSE_NOT_AUTHORIZATION_REQUIRED",
                "message": "Only expenses that require authorization can be removed during authorization review.",
            },
        )

    original_amount = Decimal(expense.amount).quantize(Decimal("0.01"))
    original_currency = expense.currency
    original_merchant = expense.merchant
    original_category = expense.category
    original_status = expense.status
    request_status_before_removal = reimbursement_request.status
    expense.status = ExpenseStatus.removed
    expense.removed_at = datetime.now(UTC)
    expense.removed_by_user_id = actor.id
    expense.removal_reason = reason
    if adjust_reported_total:
        reimbursement_request.reported_total = _active_expense_total(reimbursement_request)

    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_removed_from_request",
            message=reason,
            event_payload={
                "actor_role": actor.role.value,
                "request_status": request_status_before_removal.value,
                "original_amount": str(original_amount),
                "original_currency": original_currency,
                "original_merchant": original_merchant,
                "original_category": original_category,
                "previous_expense_status": original_status.value,
                "reported_total": str(reimbursement_request.reported_total),
                "authenticated": require_store_assignment,
            },
        )
    )
    _reject_request_if_no_payable_expenses(
        reimbursement_request,
        actor=actor,
        authenticated=require_store_assignment,
        db=db,
    )
    db.commit()
    db.refresh(expense)
    return expense


def _reject_request_if_no_payable_expenses(
    reimbursement_request: ReimbursementRequest,
    *,
    actor: User,
    authenticated: bool,
    db: Session,
) -> None:
    summary = summarize_reimbursement_request(reimbursement_request)
    if summary.expense_count > 0:
        return

    from_status, to_status = transition_reimbursement_request(
        reimbursement_request,
        actor=actor,
        target_status=ReimbursementRequestStatus.rejected,
        summary=summary,
    )
    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="request_status_changed",
            from_status=from_status.value,
            to_status=to_status.value,
            message="Solicitud rechazada automáticamente: no quedan gastos activos.",
            event_payload={
                "ready_for_submission": summary.ready_for_submission,
                "ready_for_authorization_approval": summary.ready_for_authorization_approval,
                "ready_for_accounting_approval": summary.ready_for_accounting_approval,
                "authenticated": authenticated,
                "automatic": True,
                "reason": "no_payable_expenses",
            },
        )
    )


def _apply_expense_updates(expense: Expense, updates: dict[str, object], db: Session) -> None:
    _reject_null_fields(updates, {"merchant", "amount", "currency", "spent_on"})

    period = db.get(Period, expense.period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERIOD_CLOSED", "message": "The reimbursement period is closed"},
        )

    spent_on = updates.get("spent_on", expense.spent_on)
    if not period.starts_on <= spent_on <= period.ends_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "EXPENSE_OUTSIDE_PERIOD",
                "message": "The expense date is outside the reimbursement period",
            },
        )

    for field, value in updates.items():
        setattr(expense, field, value)

    if {"amount", "currency", "supplier_tax_id"} & set(updates):
        _clear_current_cfdi_validation(db, expense)


def _clear_current_cfdi_validation(db: Session, expense: Expense) -> None:
    db.execute(
        update(CfdiValidation)
        .where(CfdiValidation.expense_id == expense.id, CfdiValidation.is_current.is_(True))
        .values(is_current=False)
    )
    expense.cfdi_uuid = None
    expense.cfdi_issuer_rfc = None
    expense.cfdi_receiver_rfc = None
    expense.cfdi_total = None
    expense.cfdi_currency = None


def _get_expense_or_404(expense_id: UUID, db: Session) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


def _attached_request_or_conflict(expense: Expense) -> ReimbursementRequest:
    if expense.reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXPENSE_NOT_ATTACHED_TO_REQUEST",
                "message": "The expense is not attached to a reimbursement request.",
            },
        )
    return expense.reimbursement_request


def _ensure_request_editable(reimbursement_request: ReimbursementRequest, *, message: str) -> None:
    if not is_request_editable(reimbursement_request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": message,
            },
        )


def _get_actor_or_404(actor_user_id: UUID, db: Session) -> User:
    actor = db.get(User, actor_user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actor user not found")
    if not actor.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ACTOR_INACTIVE", "message": "Actor user is inactive."},
        )
    return actor


def _ensure_actor_can(actor: User, roles: set[UserRole]) -> None:
    if actor.role not in roles:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ROLE_NOT_ALLOWED",
                "message": f"Role {actor.role.value} cannot perform this expense action.",
            },
        )


def _ensure_store_assignment_if_required(
    db: Session,
    actor: User,
    reimbursement_request: ReimbursementRequest,
    required: bool,
) -> None:
    if not required:
        return
    if user_can_transition_store_request(db, actor, reimbursement_request.store_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "STORE_ASSIGNMENT_REQUIRED",
            "message": "Actor must be assigned to the request store for this action",
        },
    )


def _ensure_expense_not_excluded(expense: Expense) -> None:
    if expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected} or expense.removed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXPENSE_EXCLUDED",
                "message": "Removed or rejected expenses cannot be changed.",
            },
        )


def _active_expense_total(reimbursement_request: ReimbursementRequest) -> Decimal:
    total = Decimal("0.00")
    for expense in reimbursement_request.expenses:
        if expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected} or expense.removed_at is not None:
            continue
        total += Decimal(expense.amount)
    return total.quantize(Decimal("0.01"))


def _reject_null_fields(updates: dict[str, object], fields: set[str]) -> None:
    null_fields = sorted(field for field in fields if field in updates and updates[field] is None)
    if null_fields:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "NULL_NOT_ALLOWED",
                "message": f"These fields cannot be null: {', '.join(null_fields)}",
            },
        )
