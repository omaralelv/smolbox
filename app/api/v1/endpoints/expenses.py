from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit_log import AuditActorType, AuditLog
from app.models.cfdi_validation import CfdiValidation
from app.models.expense import Expense, ExpenseStatus
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.schemas.expense import (
    ExpenseAuthorization,
    ExpenseCreate,
    ExpenseObservation,
    ExpenseRead,
    ExpenseRemoval,
    ExpenseReviewUpdate,
    ExpenseUpdate,
)

router = APIRouter()

EDITABLE_REQUEST_STATUSES = {
    ReimbursementRequestStatus.draft,
    ReimbursementRequestStatus.correction_required,
}

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

REMOVAL_ROLES_BY_STATUS = REVIEW_EDIT_ROLES_BY_STATUS


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
    reimbursement_request = _attached_request_or_conflict(expense)
    if reimbursement_request.status != ReimbursementRequestStatus.authorization_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_IN_AUTHORIZATION_REVIEW",
                "message": "Expenses can only be authorized during authorization review.",
            },
        )
    actor = _get_actor_or_404(authorization_in.actor_user_id, db)
    _ensure_actor_can(actor, {UserRole.authorizer, UserRole.admin})
    _ensure_expense_not_removed(expense)

    expense.requires_authorization = True
    expense.authorized_at = datetime.now(UTC)
    expense.authorized_by_user_id = actor.id
    expense.authorization_note = authorization_in.note
    expense.status = ExpenseStatus.approved
    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_authorized",
            message=authorization_in.note,
            event_payload={"actor_role": actor.role.value},
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/observation", response_model=ExpenseRead)
def add_expense_observation(
    expense_id: UUID,
    observation_in: ExpenseObservation,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    reimbursement_request = _attached_request_or_conflict(expense)
    actor = _get_actor_or_404(observation_in.actor_user_id, db)
    _ensure_actor_can(actor, OBSERVATION_ROLES_BY_STATUS.get(reimbursement_request.status, set()))
    _ensure_expense_not_removed(expense)

    expense.review_note = observation_in.note
    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_observation_added",
            message=observation_in.note,
            event_payload={
                "actor_role": actor.role.value,
                "request_status": reimbursement_request.status.value,
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.patch("/{expense_id}/review", response_model=ExpenseRead)
def review_update_expense(
    expense_id: UUID,
    expense_in: ExpenseReviewUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    reimbursement_request = _attached_request_or_conflict(expense)
    actor = _get_actor_or_404(expense_in.actor_user_id, db)
    _ensure_actor_can(actor, REVIEW_EDIT_ROLES_BY_STATUS.get(reimbursement_request.status, set()))
    _ensure_expense_not_removed(expense)

    updates = expense_in.model_dump(exclude_unset=True)
    note = updates.pop("note", None)
    updates.pop("actor_user_id", None)
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
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.post("/{expense_id}/remove", response_model=ExpenseRead)
def remove_expense_from_review(
    expense_id: UUID,
    removal_in: ExpenseRemoval,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = _get_expense_or_404(expense_id, db)
    reimbursement_request = _attached_request_or_conflict(expense)
    actor = _get_actor_or_404(removal_in.actor_user_id, db)
    _ensure_actor_can(actor, REMOVAL_ROLES_BY_STATUS.get(reimbursement_request.status, set()))
    _ensure_expense_not_removed(expense)

    expense.status = ExpenseStatus.removed
    expense.removed_at = datetime.now(UTC)
    expense.removed_by_user_id = actor.id
    expense.removal_reason = removal_in.reason
    if removal_in.adjust_reported_total:
        reimbursement_request.reported_total = _active_expense_total(reimbursement_request)

    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_removed_from_request",
            message=removal_in.reason,
            event_payload={
                "actor_role": actor.role.value,
                "request_status": reimbursement_request.status.value,
                "reported_total": str(reimbursement_request.reported_total),
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update_expense(
    expense_id: UUID,
    expense_in: ExpenseUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Expense:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

    if (
        expense.reimbursement_request is not None
        and expense.reimbursement_request.status not in EDITABLE_REQUEST_STATUSES
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": "Expenses can only be edited while the request is draft or in correction.",
            },
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


def _ensure_expense_not_removed(expense: Expense) -> None:
    if expense.status == ExpenseStatus.removed or expense.removed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXPENSE_REMOVED",
                "message": "Removed expenses cannot be changed.",
            },
        )


def _active_expense_total(reimbursement_request: ReimbursementRequest) -> Decimal:
    total = Decimal("0.00")
    for expense in reimbursement_request.expenses:
        if expense.status == ExpenseStatus.removed or expense.removed_at is not None:
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
