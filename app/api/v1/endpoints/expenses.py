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
from app.models.store import Store
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
from app.services.authorization_areas import user_can_authorize_expense_area
from app.services.expense_authorization_rules import (
    category_requires_manual_authorization_area,
    resolve_expense_authorization,
)
from app.services.frontend_actions import ACTION_LABELS
from app.services.permissions import user_can_transition_store_request
from app.services.reimbursement_periods import (
    ExpenseOutsideReimbursementPeriod,
    ReimbursementPeriodBoundaryUnavailable,
    validate_expense_date_for_reimbursement,
)
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.request_editability import is_request_editable
from app.services.tax_rules import (
    categoria_tiene_iva_cero_por_regla,
    determinar_indice_iva_manual,
    determinar_tasa_iva_para_gasto,
    normalizar_porcentaje_iva,
)
from app.services.workflow import transition_reimbursement_request

router = APIRouter()

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

OBSERVATION_LOCKED_STATUSES = {
    ReimbursementRequestStatus.paid,
    ReimbursementRequestStatus.closed,
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
    reimbursement_request = None

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
            raise HTTPException(...)
        try:
            validate_expense_date_for_reimbursement(
                expense_data["spent_on"],
                previous_ends_on=reimbursement_request.previous_reimbursement_ends_on,
            )
        except ExpenseOutsideReimbursementPeriod as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "EXPENSE_OUTSIDE_PERIOD",
                    "message": "El gasto está fuera de periodo.",
                },
            ) from exc
        except ReimbursementPeriodBoundaryUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "REIMBURSEMENT_PERIOD_UNAVAILABLE",
                    "message": "No se pudo validar el periodo. Contacta a soporte.",
                },
            ) from exc

    period = db.get(Period, expense_data["period_id"])
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if period.status == PeriodStatus.closed:
        raise HTTPException(...)

    if (
        category_requires_manual_authorization_area(expense_data.get("category"))
        and expense_data.get("authorization_area_id") is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "AUTHORIZATION_AREA_REQUIRED",
                "message": "Selecciona el área que autoriza para Pasajes y Taxis.",
            },
        )

    authorization_decision = resolve_expense_authorization(
        db,
        explicit=bool(expense_data.get("requires_authorization", False)),
        category=expense_data.get("category"),
        amount=expense_data.get("amount"),
        description=expense_data.get("description"),
        merchant=expense_data.get("merchant"),
        authorization_area_id=expense_data.get("authorization_area_id"),
        store_code=_store_code_for_request(reimbursement_request, db),
    )
    expense_data["requires_authorization"] = authorization_decision.requires_authorization
    if (
        expense_data.get("authorization_area_id") is None
        and authorization_decision.authorization_area_id is not None
    ):
        expense_data["authorization_area_id"] = authorization_decision.authorization_area_id
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
                message=f"Expense created for {_expense_display_name(expense)}.",
                event_payload={
                    "expense_name": _expense_display_name(expense),
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


def _expense_display_name(expense: Expense) -> str:
    return f"Gasto - {expense.category or 'Gasto General'}"


def _add_expense_button_selected_audit_event(
    db: Session,
    *,
    reimbursement_request: ReimbursementRequest,
    expense: Expense,
    actor: User,
    action_key: str,
    authenticated: bool,
) -> None:
    button_label = ACTION_LABELS.get(action_key, action_key)
    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="button_selected",
            message=f"Botón seleccionado: {button_label}.",
            event_payload={
                "action_key": action_key,
                "button_label": button_label,
                "request_status": reimbursement_request.status.value,
                "authenticated": authenticated,
            },
        )
    )


def _remove_expense_action_key(request_status: ReimbursementRequestStatus) -> str:
    if request_status == ReimbursementRequestStatus.authorization_review:
        return "remove_authorization_expense"
    return "remove_expense"


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
    changed_fields = sorted(updates)
    _apply_expense_updates(expense, updates, db)
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
    _ensure_store_assignment_if_required(
        db,
        actor,
        reimbursement_request,
        require_store_assignment,
        expense=expense,
    )
    _ensure_authorization_area_allowed(db, actor, expense)
    _ensure_expense_not_excluded(expense)

    expense.requires_authorization = True
    expense.authorized_at = datetime.now(UTC)
    expense.authorized_by_user_id = actor.id
    expense.authorization_note = note
    expense.status = ExpenseStatus.approved
    _add_expense_button_selected_audit_event(
        db,
        reimbursement_request=reimbursement_request,
        expense=expense,
        actor=actor,
        action_key="authorize_expense",
        authenticated=require_store_assignment,
    )
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
    _ensure_store_assignment_if_required(
        db,
        actor,
        reimbursement_request,
        require_store_assignment,
        expense=expense,
    )
    _ensure_authorization_area_allowed(db, actor, expense)
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

    _add_expense_button_selected_audit_event(
        db,
        reimbursement_request=reimbursement_request,
        expense=expense,
        actor=actor,
        action_key="reject_expense",
        authenticated=require_store_assignment,
    )
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
    _reject_request_if_no_payable_expenses(
        reimbursement_request,
        actor=actor,
        authenticated=require_store_assignment,
        db=db,
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
    _ensure_request_accepts_observations(reimbursement_request)
    _ensure_actor_can(actor, OBSERVATION_ROLES_BY_STATUS.get(reimbursement_request.status, set()))
    _ensure_store_assignment_if_required(
        db,
        actor,
        reimbursement_request,
        require_store_assignment,
        expense=expense,
    )
    _ensure_expense_not_excluded(expense)

    expense.review_note = note
    _add_expense_button_selected_audit_event(
        db,
        reimbursement_request=reimbursement_request,
        expense=expense,
        actor=actor,
        action_key="observe_expense",
        authenticated=require_store_assignment,
    )
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


def _ensure_request_accepts_observations(reimbursement_request: ReimbursementRequest) -> None:
    if reimbursement_request.status in OBSERVATION_LOCKED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_OBSERVATIONS_LOCKED",
                "message": "Paid requests cannot receive new observations.",
            },
        )


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
    _ensure_store_assignment_if_required(
        db,
        actor,
        reimbursement_request,
        require_store_assignment,
        expense=expense,
    )
    _ensure_expense_not_excluded(expense)

    requested_fields = set(updates)
    previous_values = _review_tracked_values(expense, db)
    _apply_expense_updates(expense, updates, db)
    new_values = _review_tracked_values(expense, db)
    changed_fields = _review_changed_fields(requested_fields, previous_values, new_values)
    changed_previous_values = _review_payload_values(previous_values, changed_fields)
    changed_new_values = _review_payload_values(new_values, changed_fields)
    event_message = (
        _review_change_message(changed_previous_values, changed_new_values)
        or note
    )
    if event_message:
        expense.review_note = event_message
    if {"amount", "currency", "supplier_tax_id", "requires_authorization"} & set(updates):
        reimbursement_request.reported_total = _active_expense_total(reimbursement_request)

    _add_expense_button_selected_audit_event(
        db,
        reimbursement_request=reimbursement_request,
        expense=expense,
        actor=actor,
        action_key="edit_expense",
        authenticated=require_store_assignment,
    )
    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_review_updated",
            message=event_message,
            event_payload={
                "actor_role": actor.role.value,
                "request_status": reimbursement_request.status.value,
                "changed_fields": changed_fields,
                "previous_values": changed_previous_values,
                "new_values": changed_new_values,
                "reported_total": str(reimbursement_request.reported_total),
                "authenticated": require_store_assignment,
            },
        )
    )
    db.commit()
    db.refresh(expense)
    return expense


def _review_tracked_values(expense: Expense, db: Session) -> dict[str, object]:
    return {
        "category": expense.category,
        "cfdi_tax_rate": _review_display_tax_rate(expense, db),
    }


def _review_display_tax_rate(expense: Expense, db: Session) -> Decimal | None:
    if expense.cfdi_tax_rate is not None:
        return expense.cfdi_tax_rate

    inferred_rate = _review_tax_rate_from_amounts(expense)
    return determinar_tasa_iva_para_gasto(
        descripcion=expense.category or "",
        numero_tienda=_store_code_for_expense(expense, db),
        porcentaje_iva=inferred_rate,
    )


def _review_tax_rate_from_amounts(expense: Expense) -> Decimal | None:
    subtotal = expense.cfdi_subtotal
    tax_amount = expense.cfdi_tax_amount
    if subtotal is None or tax_amount is None or subtotal <= Decimal("0.00"):
        return None
    try:
        return (Decimal(tax_amount) / Decimal(subtotal) * Decimal(100)).quantize(
            Decimal("0.01")
        )
    except Exception:  # noqa: BLE001
        return None


def _review_changed_fields(
    requested_fields: set[str],
    previous_values: dict[str, object],
    new_values: dict[str, object],
) -> list[str]:
    changed_fields = set(requested_fields)

    if "category" in requested_fields and _same_review_category(
        previous_values.get("category"),
        new_values.get("category"),
    ):
        changed_fields.discard("category")

    if "cfdi_tax_rate" in requested_fields and _same_review_tax_rate(
        previous_values.get("cfdi_tax_rate"),
        new_values.get("cfdi_tax_rate"),
    ):
        changed_fields.discard("cfdi_tax_rate")

    return sorted(changed_fields)


def _review_payload_values(
    values: dict[str, object],
    changed_fields: list[str],
) -> dict[str, str | None]:
    return {
        field: _serialize_review_value(field, values.get(field))
        for field in changed_fields
        if field in values
    }


def _review_change_message(
    previous_values: dict[str, str | None],
    new_values: dict[str, str | None],
) -> str | None:
    parts = []

    if "category" in previous_values and "category" in new_values:
        parts.append(
            "categoría de "
            f"{_format_review_category(previous_values['category'])} "
            f"a {_format_review_category(new_values['category'])}"
        )

    if "cfdi_tax_rate" in previous_values and "cfdi_tax_rate" in new_values:
        parts.append(
            "impuesto de "
            f"{_format_review_tax_rate(previous_values['cfdi_tax_rate'])} "
            f"a {_format_review_tax_rate(new_values['cfdi_tax_rate'])}"
        )

    if not parts:
        return None
    if len(parts) == 1:
        return f"Cambio de {parts[0]}."
    return f"Cambio de {parts[0]} e {parts[1]}."


def _same_review_category(previous: object, new: object) -> bool:
    return str(previous or "").strip().casefold() == str(new or "").strip().casefold()


def _same_review_tax_rate(previous: object, new: object) -> bool:
    previous_rate = _review_tax_rate_decimal(previous)
    new_rate = _review_tax_rate_decimal(new)
    if previous_rate is None or new_rate is None:
        return previous_rate is new_rate
    return previous_rate == new_rate


def _review_tax_rate_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    rate = Decimal(str(value))
    return rate.quantize(Decimal("0.01"))


def _serialize_review_value(field: str, value: object) -> str | None:
    if value is None:
        return None
    if field == "cfdi_tax_rate":
        return str(_review_tax_rate_decimal(value))
    return str(value)


def _format_review_category(value: str | None) -> str:
    return value or "sin categoría"


def _format_review_tax_rate(value: str | None) -> str:
    if value is None:
        return "sin impuesto"
    rate = Decimal(value).normalize()
    return f"{rate}%"


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
    if reimbursement_request.status == ReimbursementRequestStatus.authorization_review:
        _ensure_authorization_area_allowed(db, actor, expense)

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

    _add_expense_button_selected_audit_event(
        db,
        reimbursement_request=reimbursement_request,
        expense=expense,
        actor=actor,
        action_key=_remove_expense_action_key(request_status_before_removal),
        authenticated=require_store_assignment,
    )
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

    if "spent_on" in updates and expense.reimbursement_request is not None:
        try:
            validate_expense_date_for_reimbursement(
                updates["spent_on"],
                previous_ends_on=(
                    expense.reimbursement_request.previous_reimbursement_ends_on
                ),
            )
        except ExpenseOutsideReimbursementPeriod as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "EXPENSE_OUTSIDE_PERIOD",
                    "message": "El gasto está fuera de periodo.",
                },
            ) from exc
        except ReimbursementPeriodBoundaryUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "REIMBURSEMENT_PERIOD_UNAVAILABLE",
                    "message": "No se pudo validar el periodo. Contacta a soporte.",
                },
            ) from exc

    period = db.get(Period, expense.period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "PERIOD_CLOSED",
                "message": "The reimbursement period is closed",
            },
        )

    _apply_tax_rate_update(expense, updates, db)

    for field, value in updates.items():
        setattr(expense, field, value)

    if {"amount", "currency", "supplier_tax_id"} & set(updates):
        _clear_current_cfdi_validation(db, expense)


def _apply_tax_rate_update(expense: Expense, updates: dict[str, object], db: Session) -> None:
    rate_was_explicit = "cfdi_tax_rate" in updates
    category_was_changed = (
        "category" in updates and updates["category"] != expense.category
    )
    if not rate_was_explicit and not category_was_changed:
        return

    amount = Decimal(updates.get("amount", expense.amount)).quantize(Decimal("0.01"))
    category = str(updates.get("category") or expense.category or "")
    if rate_was_explicit:
        tax_rate = updates["cfdi_tax_rate"]
        if tax_rate is None:
            updates["cfdi_tax_amount"] = None
            updates["cfdi_subtotal"] = None
            updates["sap_tax_index_override"] = None
            return
        if not isinstance(tax_rate, Decimal):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="cfdi_tax_rate must be a decimal percentage",
            )
        rate = normalizar_porcentaje_iva(tax_rate)
        if rate is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="cfdi_tax_rate must be a valid decimal percentage",
            )
        updates["sap_tax_index_override"] = determinar_indice_iva_manual(rate)
    else:
        rate_base = expense.cfdi_tax_rate
        category_was_automatically_zero = (
            expense.cfdi_tax_rate == Decimal("0.00")
            and categoria_tiene_iva_cero_por_regla(expense.category or "")
        )
        category_had_manual_override = expense.sap_tax_index_override is not None
        if category_had_manual_override or (
            category_was_automatically_zero
            and not categoria_tiene_iva_cero_por_regla(category)
        ):
            rate_base = Decimal("16.00")
        rate = determinar_tasa_iva_para_gasto(
            descripcion=category,
            numero_tienda=_store_code_for_expense(expense, db),
            porcentaje_iva=rate_base,
        )
        updates["cfdi_tax_rate"] = rate
        updates["sap_tax_index_override"] = None

    tax_amount = (
        amount
        / (Decimal(1) + rate / Decimal(100))
        * (rate / Decimal(100))
    ).quantize(Decimal("0.01"))

    updates["cfdi_tax_rate"] = rate
    updates["cfdi_tax_amount"] = tax_amount
    updates["cfdi_subtotal"] = (amount - tax_amount).quantize(Decimal("0.01"))
    updates["cfdi_total"] = amount
    updates["cfdi_currency"] = str(updates.get("currency", expense.currency)).upper()


def _store_code_for_expense(expense: Expense, db: Session) -> str:
    request = expense.reimbursement_request
    if request is None and expense.reimbursement_request_id is not None:
        request = db.get(ReimbursementRequest, expense.reimbursement_request_id)
    return _store_code_for_request(request, db)


def _store_code_for_request(request: ReimbursementRequest | None, db: Session) -> str:
    if request is None:
        return ""

    store = request.store or db.get(Store, request.store_id)
    return str(store.code) if store else ""


def _clear_current_cfdi_validation(db: Session, expense: Expense) -> None:
    db.execute(
        update(CfdiValidation)
        .where(CfdiValidation.expense_id == expense.id, CfdiValidation.is_current.is_(True))
        .values(is_current=False)
    )
    expense.cfdi_uuid = None
    expense.cfdi_issuer_rfc = None
    expense.cfdi_receiver_rfc = None
    expense.cfdi_subtotal = None
    expense.cfdi_total = None
    expense.cfdi_currency = None
    expense.cfdi_tax_amount = None
    expense.cfdi_tax_rate = None
    expense.sap_tax_index_override = None


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
    *,
    expense: Expense | None = None,
) -> None:
    if not required:
        return
    if user_can_transition_store_request(db, actor, reimbursement_request.store_id):
        return
    if (
        actor.role == UserRole.authorizer
        and expense is not None
        and user_can_authorize_expense_area(
            db,
            actor,
            expense,
            store_id=reimbursement_request.store_id,
        )
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "STORE_ASSIGNMENT_REQUIRED",
            "message": "Actor must be assigned to the request store for this action",
        },
    )


def _ensure_authorization_area_allowed(db: Session, actor: User, expense: Expense) -> None:
    reimbursement_request = _attached_request_or_conflict(expense)
    if user_can_authorize_expense_area(
        db,
        actor,
        expense,
        store_id=reimbursement_request.store_id,
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "AUTHORIZATION_AREA_FORBIDDEN",
            "message": "Actor cannot authorize expenses for this authorization area.",
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
