from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense, ExpenseStatus
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import (
    AccountingQueueStatus,
    ReimbursementRequest,
    ReimbursementRequestStatus,
)
from app.models.store import Store, StoreUserAssignment
from app.models.store_spending_baseline import StoreSpendingBaseline
from app.models.user import User, UserRole
from app.schemas.frontend import (
    FrontendContextRead,
    FrontendGastoCreate,
    FrontendGastoRead,
    FrontendManagementProductivityDashboardRead,
    FrontendManagementProductivityRowRead,
    FrontendObservationCreate,
    FrontendSolicitudCreate,
    FrontendSolicitudRead,
    FrontendStoreRead,
    FrontendTreasuryDashboardRead,
    FrontendTreasuryDashboardRowRead,
    FrontendTreasuryDashboardStoreRead,
    FrontendUserRead,
)
from app.services.accounting_queue import mark_accounting_request_taken_on_open
from app.services.authorization_areas import (
    expense_is_visible_to_authorizer,
    get_or_create_authorization_area,
    request_has_authorization_area_for_user,
    request_has_authorization_visible_to_user,
)
from app.services.expense_authorization_rules import expense_requires_authorization
from app.services.frontend_actions import available_actions_for_request
from app.services.permissions import user_can_transition_store_request, user_has_store_assignment
from app.services.reimbursement_periods import (
    obtener_contexto_periodo_reembolso,
)
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.tax_rules import cargar_tiendas_iva_w6, determinar_iva_e_indice
from app.utils.folio_dates import (
    obtener_fecha_desde_folio,
)

router = APIRouter()
ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"
TIENDAS_IVA_W6_FILES = (
    "tiendas_iva_w6.xlsx",
    "TDAS IVA W6.xlsx",
)
MEXICO_CITY_TZ = ZoneInfo(
    "America/Mexico_City"
)
ROLE_TO_FRONTEND = {
    UserRole.store: "tienda",
    UserRole.authorizer: "supervisor",
    UserRole.accountant: "contabilidad",
    UserRole.accounting_manager: "gerencia",
    UserRole.treasury: "tesoreria",
    UserRole.director: "direccion",
    UserRole.admin: "admin",
}

ROLE_QUEUE_STATUSES: dict[UserRole, set[ReimbursementRequestStatus]] = {
    UserRole.store: {
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
        ReimbursementRequestStatus.accounting_reviewed,
    },
    UserRole.accounting_manager: {
        ReimbursementRequestStatus.accounting_manager_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
    },
    UserRole.treasury: {
        ReimbursementRequestStatus.accounting_manager_approved,
        ReimbursementRequestStatus.treasury_review,
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
    },
    UserRole.director: {
        ReimbursementRequestStatus.direction_review,
        ReimbursementRequestStatus.direction_approved,
    },
}

STORE_MONITORING_STATUSES = {
    ReimbursementRequestStatus.submitted,
    ReimbursementRequestStatus.authorization_review,
    ReimbursementRequestStatus.authorized,
    ReimbursementRequestStatus.under_accounting_review,
    ReimbursementRequestStatus.correction_required,
    ReimbursementRequestStatus.accounting_reviewed,
    ReimbursementRequestStatus.accounting_approved,
    ReimbursementRequestStatus.accounting_manager_review,
    ReimbursementRequestStatus.accounting_manager_approved,
    ReimbursementRequestStatus.treasury_review,
    ReimbursementRequestStatus.direction_review,
    ReimbursementRequestStatus.direction_approved,
    ReimbursementRequestStatus.approved_for_payment,
}

HISTORICAL_STATUSES = {
    ReimbursementRequestStatus.paid,
    ReimbursementRequestStatus.closed,
    ReimbursementRequestStatus.rejected,
}

TREASURY_DASHBOARD_SPENDING_STATUSES = {
    ReimbursementRequestStatus.direction_approved,
    ReimbursementRequestStatus.approved_for_payment,
    ReimbursementRequestStatus.paid,
    ReimbursementRequestStatus.closed,
}

GLOBAL_POST_ACCOUNTING_ROLES = {
    UserRole.accounting_manager,
    UserRole.treasury,
    UserRole.director,
}

ACTION_LABELS = {
    "edit_request": "Editar solicitud",
    "add_expense": "Añadir gasto",
    "upload_request_attachment": "Cargar reembolso",
    "submit_request": "Enviar solicitud",
    "start_authorization_review": "Iniciar autorización",
    "authorize_expense": "Autorizar gasto",
    "reject_expense": "Rechazar gasto",
    "remove_authorization_expense": "Eliminar gasto",
    "approve_authorization": "Autorizar solicitud",
    "start_accounting_review": "Revisión contable",
    "edit_expense": "Editar gasto",
    "observe_expense": "Observaciones",
    "remove_expense": "Eliminar gasto",
    "prepare_sap_policy": "Póliza y Reembolso",
    "mark_accounting_reviewed": "Cerrar contabilidad",
    "start_accounting_manager_review": "Enviar a Juanita",
    "approve_accounting_manager": "Enviar a Samuel",
    "return_to_accounting": "Regresar acumulado",
    "start_treasury_review": "Revisión tesorería",
    "send_to_direction": "Enviar Dirección",
    "return_to_manager": "Regresar acumulado",
    "approve_direction": "Aprobar pago",
    "return_to_treasury": "Regresar acumulado",
    "mark_approved_for_payment": "Aprobar pago",
    "record_payment": "Confirmar pago",
    "close_request": "Cerrar solicitud",
    "reject_request": "Rechazar solicitud",
}


@router.get("/context/me", response_model=FrontendContextRead)
def get_frontend_context(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendContextRead:
    stores = _stores_for_user(current_user, db)
    active_store = stores[0] if stores else None
    current_period = _current_open_period(db)
    return FrontendContextRead(
        current_role=_frontend_role(current_user.role),
        backend_role=current_user.role.value,
        usuario=FrontendUserRead(
            id=current_user.id,
            email=current_user.email,
            nombre=current_user.full_name,
            rol=_frontend_role(current_user.role),
            backend_role=current_user.role.value,
        ),
        stores=[_store_payload(store) for store in stores],
        active_store=_store_payload(active_store) if active_store else None,
        current_period_id=current_period.id if current_period else None,
        tienda=active_store.code if active_store else None,
        gerente=active_store.manager_name if active_store else None,
        cuenta_bancaria=active_store.bank_account if active_store else None,
        estado_region=active_store.state_region if active_store else None,
    )


@router.get("/bandeja/me", response_model=list[FrontendSolicitudRead])
def list_frontend_work_queue(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FrontendSolicitudRead]:
    statement = _request_detail_statement().order_by(ReimbursementRequest.created_at.desc())
    if current_user.role == UserRole.store:
        statement = statement.where(ReimbursementRequest.status.in_(STORE_MONITORING_STATUSES))
        statement = statement.where(
            ReimbursementRequest.store_id.in_(
                select(StoreUserAssignment.store_id).where(
                    StoreUserAssignment.user_id == current_user.id,
                    StoreUserAssignment.role == UserRole.store,
                    StoreUserAssignment.is_active.is_(True),
                )
            )
        )
        requests = list(db.scalars(statement.limit(200)))
        return [_request_payload(request, current_user, db) for request in requests]

    if current_user.role == UserRole.admin:
        statement = statement.where(
            ReimbursementRequest.status.not_in(
                {ReimbursementRequestStatus.draft} | HISTORICAL_STATUSES
            )
        )
        requests = list(db.scalars(statement.limit(200)))
        return [_request_payload(request, current_user, db) for request in requests]

    statuses = ROLE_QUEUE_STATUSES.get(current_user.role, set())
    if not statuses:
        return []

    statement = statement.where(ReimbursementRequest.status.in_(statuses))
    if current_user.role not in {
        UserRole.accountant,
        *GLOBAL_POST_ACCOUNTING_ROLES,
    }:
        statement = statement.where(
            ReimbursementRequest.store_id.in_(
                select(StoreUserAssignment.store_id).where(
                    StoreUserAssignment.user_id == current_user.id,
                    StoreUserAssignment.role == current_user.role,
                    StoreUserAssignment.is_active.is_(True),
                )
            )
        )

    requests = [
        request
        for request in db.scalars(statement.limit(200))
        if _request_is_visible_for_role(request, current_user, db)
    ]
    return [_request_payload(request, current_user, db) for request in requests]


@router.get("/historico/me", response_model=list[FrontendSolicitudRead])
def list_frontend_historical_requests(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[FrontendSolicitudRead]:
    statement = (
        _request_detail_statement()
        .where(ReimbursementRequest.status.in_(HISTORICAL_STATUSES))
        .order_by(ReimbursementRequest.created_at.desc())
    )
    if current_user.role not in {*GLOBAL_POST_ACCOUNTING_ROLES, UserRole.admin}:
        statement = statement.where(
            ReimbursementRequest.store_id.in_(
                select(StoreUserAssignment.store_id).where(
                    StoreUserAssignment.user_id == current_user.id,
                    StoreUserAssignment.role == current_user.role,
                    StoreUserAssignment.is_active.is_(True),
                )
            )
        )

    requests = list(db.scalars(statement.limit(200)))
    return [_request_payload(request, current_user, db) for request in requests]


@router.get("/solicitudes/{request_identifier}/me", response_model=FrontendSolicitudRead)
def get_frontend_request_detail(
    request_identifier: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendSolicitudRead:
    request = _get_request_by_frontend_identifier(request_identifier, db)
    _ensure_request_visible(request, current_user, db)
    request = _mark_accounting_request_taken_if_needed(request, current_user, db)
    return _request_payload(request, current_user, db)


@router.get("/tesoreria/dashboard/me", response_model=FrontendTreasuryDashboardRead)
def get_treasury_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendTreasuryDashboardRead:
    if current_user.role not in {*GLOBAL_POST_ACCOUNTING_ROLES, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only post-accounting roles can view the treasury dashboard",
            },
        )

    current_year = datetime.now(MEXICO_CITY_TZ).year
    years = [current_year - 2, current_year - 1, current_year]
    stores = list(db.scalars(select(Store).order_by(Store.code)))
    store_ids = [store.id for store in stores]
    values_by_store = {
        store.id: {year: Decimal("0.00") for year in years}
        for store in stores
    }

    if store_ids:
        baseline_rows = db.execute(
            select(
                StoreSpendingBaseline.store_id,
                StoreSpendingBaseline.fiscal_year,
                StoreSpendingBaseline.historical_amount,
            )
            .where(
                StoreSpendingBaseline.store_id.in_(store_ids),
                StoreSpendingBaseline.fiscal_year.in_(years),
            )
        )
        for store_id, fiscal_year, historical_amount in baseline_rows:
            values_by_store[store_id][int(fiscal_year)] += _money(historical_amount)

        expense_year = func.extract("year", Expense.spent_on)
        approved_rows = db.execute(
            select(
                ReimbursementRequest.store_id,
                expense_year.label("expense_year"),
                func.coalesce(func.sum(Expense.amount), Decimal("0.00")),
            )
            .join(Expense, Expense.reimbursement_request_id == ReimbursementRequest.id)
            .where(
                ReimbursementRequest.store_id.in_(store_ids),
                ReimbursementRequest.status.in_(TREASURY_DASHBOARD_SPENDING_STATUSES),
                Expense.status.not_in({ExpenseStatus.removed, ExpenseStatus.rejected}),
                Expense.removed_at.is_(None),
                expense_year.in_(years),
            )
            .group_by(ReimbursementRequest.store_id, expense_year)
        )
        for store_id, fiscal_year, approved_amount in approved_rows:
            values_by_store[store_id][int(fiscal_year)] += _money(approved_amount)

    return FrontendTreasuryDashboardRead(
        years=years,
        stores=[
            FrontendTreasuryDashboardStoreRead(
                id=store.id,
                code=_frontend_store_code(store),
                name=store.name,
            )
            for store in stores
        ],
        rows=[
            FrontendTreasuryDashboardRowRead(
                store_id=store.id,
                store_code=_frontend_store_code(store),
                store_name=store.name,
                values={
                    year: float(_money(values_by_store[store.id][year]))
                    for year in years
                },
            )
            for store in stores
        ],
    )


@router.get("/gerencia/productividad/me", response_model=FrontendManagementProductivityDashboardRead)
def get_management_productivity_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendManagementProductivityDashboardRead:
    if current_user.role not in {UserRole.accounting_manager, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only management users can view the productivity dashboard",
            },
        )

    day_labels = ["Lu", "Ma", "Mi", "Ju", "Vi"]
    today = datetime.now(MEXICO_CITY_TZ).date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4)
    window_start = datetime.combine(week_start, time.min, tzinfo=MEXICO_CITY_TZ)
    window_end = datetime.combine(week_start + timedelta(days=7), time.min, tzinfo=MEXICO_CITY_TZ)

    accountants = list(
        db.scalars(
            select(User)
            .where(
                User.role == UserRole.accountant,
                User.is_active.is_(True),
            )
            .order_by(User.full_name)
        )
    )
    values_by_accountant = {
        accountant.id: {day: 0 for day in day_labels}
        for accountant in accountants
    }

    event_rows = db.execute(
        select(
            AuditLog.actor_user_id,
            AuditLog.created_at,
        )
        .join(User, AuditLog.actor_user_id == User.id)
        .where(
            AuditLog.action == "request_status_changed",
            AuditLog.to_status == ReimbursementRequestStatus.accounting_reviewed.value,
            AuditLog.created_at >= window_start,
            AuditLog.created_at < window_end,
            User.role == UserRole.accountant,
        )
    )

    for accountant_id, created_at in event_rows:
        if accountant_id not in values_by_accountant:
            continue
        event_timestamp = created_at
        if event_timestamp.tzinfo is None:
            event_timestamp = event_timestamp.replace(tzinfo=UTC)
        weekday = event_timestamp.astimezone(MEXICO_CITY_TZ).weekday()
        if 0 <= weekday < len(day_labels):
            values_by_accountant[accountant_id][day_labels[weekday]] += 1

    totals = {day: 0 for day in day_labels}
    rows = []
    for accountant in accountants:
        values = values_by_accountant[accountant.id]
        total = sum(values.values())
        for day, value in values.items():
            totals[day] += value
        rows.append(
            FrontendManagementProductivityRowRead(
                accountant_id=accountant.id,
                accountant_name=accountant.full_name,
                values=values,
                total=total,
            )
        )

    return FrontendManagementProductivityDashboardRead(
        week_starts_on=week_start,
        week_ends_on=week_end,
        days=day_labels,
        rows=rows,
        totals=totals,
        grand_total=sum(totals.values()),
    )


@router.post(
    "/solicitudes/me",
    response_model=FrontendSolicitudRead,
    status_code=status.HTTP_201_CREATED,
)
def create_frontend_request(
    request_in: FrontendSolicitudCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendSolicitudRead:
    if current_user.role not in {UserRole.store, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only store or admin users can create reimbursement requests",
            },
        )

    store = _resolve_store_for_create(
        request_in,
        current_user,
        db,
    )

    period = _resolve_period_for_create(
        request_in,
        db,
    )

    folio = _generate_request_folio(
        store,
        db,
    )
    fecha_fin_reembolso = obtener_fecha_desde_folio(
        folio
    )

    try:
        fecha_fin_reembolso = (
            obtener_fecha_desde_folio(folio)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INVALID_GENERATED_FOLIO",
                "message": (
                    "No se pudo obtener la fecha "
                    "del folio generado."
                ),
            },
        ) from exc

    try:
        contexto_periodo = (
            obtener_contexto_periodo_reembolso(
                db=db,
                store_id=store.id,
                fecha_fin_actual=fecha_fin_reembolso,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_REIMBURSEMENT_PERIOD",
                "message": str(exc),
            },
        ) from exc
    reported_total = request_in.reported_total
    if reported_total is None:
        reported_total = sum((expense.monto for expense in request_in.gastos), Decimal("0.00"))

    request = ReimbursementRequest(
        store_id=store.id,
        period_id=period.id,
        reported_total=_money(reported_total),
        notes=request_in.notes,

        folio=folio,

        reimbursement_starts_on=(
            contexto_periodo.current_starts_on
        ),

        reimbursement_ends_on=fecha_fin_reembolso,

        previous_reimbursement_request_id=(
            contexto_periodo.previous_request_id
        ),

        previous_reimbursement_starts_on=(
            contexto_periodo.previous_starts_on
        ),

        previous_reimbursement_ends_on=(
            contexto_periodo.previous_ends_on
        ),

        previous_reimbursement_amount=(
            contexto_periodo.previous_amount
        ),
    )
    db.add(request)
    db.flush()
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="request_created_from_frontend",
            to_status=request.status.value,
            message="Reimbursement request created from frontend-compatible API.",
        )
    )

    for expense_in in request_in.gastos:
        expense = _expense_from_frontend(expense_in, request=request, period=period, db=db)
        db.add(expense)
        db.flush()
        _add_frontend_observation_events(
            expense_in,
            request=request,
            expense=expense,
            actor=current_user,
            db=db,
        )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "FRONTEND_REQUEST_CONFLICT",
                "message": "The request or one of its expenses conflicts with existing data",
            },
        ) from exc

    request = _get_request_by_id(request.id, db)
    return _request_payload(request, current_user, db)


@router.post(
    "/solicitudes/{request_identifier}/gastos/me",
    response_model=FrontendSolicitudRead,
    status_code=status.HTTP_201_CREATED,
)
def add_frontend_expense(
    request_identifier: str,
    expense_in: FrontendGastoCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendSolicitudRead:
    request = _get_request_by_frontend_identifier(request_identifier, db)
    _ensure_request_visible(request, current_user, db)
    if current_user.role not in {UserRole.store, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only store or admin users can add expenses from the frontend",
            },
        )
    if request.status not in {
        ReimbursementRequestStatus.draft,
        ReimbursementRequestStatus.correction_required,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": "Expenses can only be added before submission",
            },
        )

    expense = _expense_from_frontend(expense_in, request=request, period=request.period, db=db)
    db.add(expense)
    db.flush()
    request.reported_total = _money(
        (request.reported_total or Decimal("0.00")) + expense.amount
    )
    _add_frontend_observation_events(
        expense_in,
        request=request,
        expense=expense,
        actor=current_user,
        db=db,
    )
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="expense_created_from_frontend",
            message=f"Expense created for {expense.merchant}.",
        )
    )
    db.commit()
    request = _get_request_by_id(request.id, db)
    return _request_payload(request, current_user, db)


@router.delete(
    "/solicitudes/{request_identifier}/gastos/{expense_id}/me",
    response_model=FrontendSolicitudRead,
)
def delete_frontend_draft_expense(
    request_identifier: str,
    expense_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendSolicitudRead:
    request = _get_request_by_frontend_identifier(request_identifier, db)
    _ensure_request_visible(request, current_user, db)
    if current_user.role not in {UserRole.store, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only store or admin users can delete draft expenses from the frontend",
            },
        )
    if request.status not in {
        ReimbursementRequestStatus.draft,
        ReimbursementRequestStatus.correction_required,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": "Expenses can only be deleted before submission",
            },
        )

    expense = next((item for item in request.expenses if item.id == expense_id), None)
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "EXPENSE_NOT_FOUND",
                "message": "Expense not found in this request",
            },
        )

    if expense.status != ExpenseStatus.removed or expense.removed_at is None:
        previous_expense_status = expense.status
        expense.status = ExpenseStatus.removed
        expense.removed_at = datetime.now(UTC)
        expense.removed_by_user_id = current_user.id
        expense.removal_reason = "Gasto eliminado por tienda antes de enviar la solicitud."
        request.reported_total = _active_frontend_expense_total(request)
        db.add(
            AuditLog(
                reimbursement_request_id=request.id,
                expense_id=expense.id,
                actor_user_id=current_user.id,
                actor_type=AuditActorType.user,
                action="expense_removed_from_request",
                message=expense.removal_reason,
                event_payload={
                    "actor_role": current_user.role.value,
                    "request_status": request.status.value,
                    "previous_expense_status": previous_expense_status.value,
                    "reported_total": str(request.reported_total),
                    "authenticated": True,
                    "draft_delete": True,
                },
            )
        )

    db.commit()
    request = _get_request_by_id(request.id, db)
    return _request_payload(request, current_user, db)


def _active_frontend_expense_total(request: ReimbursementRequest) -> Decimal:
    return _money(
        sum(
            (
                expense.amount
                for expense in request.expenses
                if expense.status not in {ExpenseStatus.removed, ExpenseStatus.rejected}
                and expense.removed_at is None
            ),
            Decimal("0.00"),
        )
    )


def _request_detail_statement():
    return select(ReimbursementRequest).options(
        selectinload(ReimbursementRequest.store),
        selectinload(ReimbursementRequest.period),
        selectinload(ReimbursementRequest.attachments),
        selectinload(ReimbursementRequest.expenses)
        .selectinload(Expense.attachments)
        .selectinload(Attachment.ocr_extraction),
        selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        selectinload(ReimbursementRequest.expenses).selectinload(Expense.authorization_area),
        selectinload(ReimbursementRequest.payments),
        selectinload(ReimbursementRequest.audit_events),
    )


def _stores_for_user(current_user: User, db: Session) -> list[Store]:
    if current_user.role == UserRole.admin:
        return list(db.scalars(select(Store).order_by(Store.code).limit(200)))
    return [
        assignment.store
        for assignment in db.scalars(
            select(StoreUserAssignment)
            .options(selectinload(StoreUserAssignment.store))
            .where(
                StoreUserAssignment.user_id == current_user.id,
                StoreUserAssignment.is_active.is_(True),
            )
            .order_by(StoreUserAssignment.created_at.desc())
        )
    ]


def _store_payload(store: Store) -> FrontendStoreRead:
    return FrontendStoreRead(
        id=store.id,
        code=_frontend_store_code(store),
        name=store.name,
        gerente=store.manager_name,
        cuenta_bancaria=store.bank_account,
        estado_region=store.state_region,
    )


def _request_payload(
    request: ReimbursementRequest,
    current_user: User,
    db: Session,
) -> FrontendSolicitudRead:
    summary = summarize_reimbursement_request(request)
    actions = available_actions_for_request(request, actor=current_user, summary=summary)
    display_date = _request_display_date(request)
    folio = request.folio or f"Solicitud {str(request.id)[:8]}"
    calculated_total = _money(summary.calculated_total)
    reported_total = _money(request.reported_total) if request.reported_total is not None else None
    reembolso_attachment = _latest_reembolso_attachment(request)
    return FrontendSolicitudRead(
        id=folio,
        backend_id=request.id,
        folio=folio,
        tienda=_frontend_store_code(request.store),
        fecha=_format_date(display_date),
        fecha_formateada=display_date.strftime("%d%m%Y"),
        status=_frontend_request_status(request.status),
        backend_status=request.status.value,
        accounting_queue_status=_frontend_accounting_queue_status(request, current_user),
        gerente=request.store.manager_name,
        cuenta_bancaria=request.store.bank_account,
        estado_region=request.store.state_region,
        gastos=[
            _expense_payload(expense)
            for expense in sorted(
                _frontend_visible_expenses(request.expenses, current_user, db),
                key=_expense_sort_key,
            )
        ],
        monto_total=float(calculated_total),
        reported_total=float(reported_total) if reported_total is not None else None,
        calculated_total=float(calculated_total),
        expense_count=summary.expense_count,
        reembolso_attachment_id=reembolso_attachment.id if reembolso_attachment else None,
        reembolso_file_name=reembolso_attachment.filename if reembolso_attachment else None,
        reembolso_download_url=_attachment_download_url(reembolso_attachment),
        available_actions=actions,
        action_labels={action: ACTION_LABELS.get(action, action) for action in actions},
    )


def _frontend_accounting_queue_status(
    request: ReimbursementRequest,
    current_user: User,
) -> str | None:
    queue_status = request.accounting_queue_status
    if queue_status is None:
        return None
    if queue_status != AccountingQueueStatus.taken:
        return queue_status.value
    if (
        current_user.role in {UserRole.accountant, UserRole.admin}
        and request.accounting_queue_taken_by_user_id != current_user.id
    ):
        return "taken_other"
    return queue_status.value


def _frontend_visible_expenses(
    expenses: list[Expense],
    current_user: User,
    db: Session,
) -> list[Expense]:
    return [
        expense
        for expense in expenses
        if expense_is_visible_to_authorizer(db, current_user, expense)
    ]


def _expense_payload(expense: Expense) -> FrontendGastoRead:
    category = expense.category or "Gasto General"
    folio = expense.cfdi_uuid or _suggested_cfdi_uuid_from_ocr(expense) or "N/A"
    document_urls = _expense_document_urls(expense)
    return FrontendGastoRead(
        id=str(expense.id),
        backend_id=expense.id,
        nombre=f"Gasto - {category}",
        monto=float(_money(expense.amount)),
        tipo=category,
        type=category,
        folio=folio,
        folio_fiscal=expense.cfdi_uuid,
        observaciones=expense.description or "",
        cfdi_subtotal=_float_or_none(expense.cfdi_subtotal),
        cfdi_total=_float_or_none(expense.cfdi_total),
        cfdi_tax_amount=_float_or_none(expense.cfdi_tax_amount),
        cfdi_tax_rate=_float_or_none(expense.cfdi_tax_rate),
        cfdi_currency=expense.cfdi_currency,
        facturas=_invoice_count(expense),
        autorizacion=_frontend_authorization_status(expense),
        status=_frontend_expense_status(expense.status),
        backend_status=expense.status.value,
        requires_authorization=expense.requires_authorization,
        authorization_area_id=expense.authorization_area_id,
        authorization_area_name=(
            expense.authorization_area.name if expense.authorization_area else None
        ),
        download_url=(
            document_urls["url_recibo"]
            or document_urls["url_factura"]
            or document_urls["url_vale"]
        ),
        url_factura=document_urls["url_factura"],
        url_vale=document_urls["url_vale"],
        url_recibo=document_urls["url_recibo"],
        url_gasto=document_urls["url_recibo"],
    )


def _resolve_store_for_create(
    request_in: FrontendSolicitudCreate,
    current_user: User,
    db: Session,
) -> Store:
    store = None
    if request_in.store_id is not None:
        store = db.get(Store, request_in.store_id)
    elif request_in.tienda:
        store = db.scalar(select(Store).where(Store.code == request_in.tienda))
        if store is None:
            store = db.scalar(select(Store).where(Store.code == f"HUD-{request_in.tienda}"))
    else:
        stores = _stores_for_user(current_user, db)
        store = stores[0] if stores else None

    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STORE_NOT_FOUND", "message": "Store was not found"},
        )
    if current_user.role != UserRole.admin and not user_has_store_assignment(
        db,
        current_user,
        store.id,
        roles={UserRole.store},
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Store users can create requests only for assigned stores",
            },
        )
    return store


def _resolve_period_for_create(request_in: FrontendSolicitudCreate, db: Session) -> Period:
    period = db.get(Period, request_in.period_id) if request_in.period_id is not None else None
    if period is None:
        period = _current_open_period(db)
    if period is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "OPEN_PERIOD_REQUIRED", "message": "There is no open period"},
        )
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERIOD_CLOSED", "message": "The reimbursement period is closed"},
        )
    return period


def _expense_from_frontend(
    expense_in: FrontendGastoCreate,
    *,
    request: ReimbursementRequest,
    period: Period,
    db: Session,
) -> Expense:
    spent_on = _parse_frontend_date(expense_in.fecha, period)

    reimbursement_starts_on = (request.reimbursement_starts_on)
    reimbursement_ends_on = (request.reimbursement_ends_on)

    if (
        reimbursement_starts_on is None
        or reimbursement_ends_on is None
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REIMBURSEMENT_COVERAGE_MISSING",
                "message": (
                    "La solicitud no tiene un periodo "
                    "de reembolso calculado."
                ),
            },
        )
    category = expense_in.categoria or "Gasto General"
    merchant = expense_in.merchant or expense_in.proveedor or f"Gasto - {category}"
    amount = _money(expense_in.monto)
    store_code = _request_store_code(request, db)
    tax_rate = _frontend_tax_rate_for_expense(
        category=category,
        store_code=store_code,
        requested_tax_rate=expense_in.cfdi_tax_rate,
    )
    tax_amount, tax_subtotal = _tax_amounts_from_rate(amount, tax_rate)
    authorization_area = None
    if expense_in.authorization_area_name:
        try:
            authorization_area = get_or_create_authorization_area(
                db,
                expense_in.authorization_area_name,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "AUTHORIZATION_AREA_NAME_INVALID",
                    "message": str(exc),
                },
            ) from exc

    return Expense(
        reimbursement_request_id=request.id,
        period_id=period.id,
        merchant=merchant,
        amount=amount,
        currency=expense_in.moneda.upper(),
        spent_on=spent_on,
        category=category,
        description=expense_in.observaciones,
        cfdi_uuid=expense_in.cfdi_uuid or expense_in.folio,
        cfdi_subtotal=tax_subtotal,
        cfdi_total=amount,
        cfdi_currency=(expense_in.cfdi_currency or expense_in.moneda).upper(),
        cfdi_tax_amount=tax_amount,
        cfdi_tax_rate=tax_rate,
        authorization_area_id=authorization_area.id if authorization_area else None,
        requires_authorization=expense_requires_authorization(
            explicit=expense_in.requiere_autorizacion,
            category=category,
            description=expense_in.observaciones,
            merchant=merchant,
        ),
    )


def _frontend_tax_rate_for_expense(
    *,
    category: str,
    store_code: str,
    requested_tax_rate: Decimal | None,
) -> Decimal:
    base_tax_rate = _rate_or_none(requested_tax_rate) or Decimal("16.00")
    tax_rate, _tax_index = determinar_iva_e_indice(
        descripcion=category,
        numero_tienda=store_code,
        porcentaje_iva=base_tax_rate,
        tiendas_iva_w6=_tiendas_iva_w6(),
    )
    return _rate_or_none(tax_rate) or Decimal("16.00")


def _tax_amounts_from_rate(amount: Decimal, tax_rate: Decimal) -> tuple[Decimal, Decimal]:
    rate = _rate_or_none(tax_rate) or Decimal("0.00")
    if rate == Decimal("0.00"):
        return Decimal("0.00"), amount

    tax_amount = (
        amount
        / (Decimal(1) + rate / Decimal(100))
        * (rate / Decimal(100))
    ).quantize(Decimal("0.01"))
    return tax_amount, (amount - tax_amount).quantize(Decimal("0.01"))


def _request_store_code(request: ReimbursementRequest, db: Session) -> str:
    store = request.store or db.get(Store, request.store_id)
    return _frontend_store_code(store) if store else ""


@lru_cache(maxsize=1)
def _tiendas_iva_w6() -> set[str]:
    for filename in TIENDAS_IVA_W6_FILES:
        path = ASSETS_DIR / filename
        if path.exists():
            return cargar_tiendas_iva_w6(str(path))
    return set()


def _add_frontend_observation_events(
    expense_in: FrontendGastoCreate,
    *,
    request: ReimbursementRequest,
    expense: Expense,
    actor: User,
    db: Session,
) -> None:
    seen: set[tuple[str, int | float | None]] = set()

    for observation in expense_in.observaciones_historial:
        note = observation.texto.strip()
        if not note:
            continue

        key = (note, observation.fecha_timestamp)
        if key in seen:
            continue
        seen.add(key)

        created_at = _frontend_observation_created_at(observation)
        audit_log = AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="expense_observation_added",
            message=note,
            event_payload={
                "actor_role": actor.role.value,
                "request_status": request.status.value,
                "source": "frontend_draft",
                "frontend_role": observation.rol,
                "frontend_author": observation.autor,
                "frontend_visibility": observation.visibilidad,
                "fecha_timestamp": observation.fecha_timestamp,
            },
        )
        if created_at is not None:
            audit_log.created_at = created_at

        db.add(
            audit_log
        )


def _frontend_observation_created_at(
    observation: FrontendObservationCreate,
) -> datetime | None:
    timestamp = observation.fecha_timestamp
    if timestamp is None:
        return None

    try:
        timestamp_value = float(timestamp)
    except (TypeError, ValueError):
        return None

    if timestamp_value > 10_000_000_000:
        timestamp_value = timestamp_value / 1000

    return datetime.fromtimestamp(timestamp_value, UTC)


def _get_request_by_frontend_identifier(
    request_identifier: str,
    db: Session,
) -> ReimbursementRequest:
    try:
        request_uuid = UUID(request_identifier)
    except ValueError:
        request_uuid = None

    if request_uuid is not None:
        return _get_request_by_id(request_uuid, db)

    request = db.scalars(
        _request_detail_statement().where(ReimbursementRequest.folio == request_identifier)
    ).first()
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REQUEST_NOT_FOUND", "message": "Reimbursement request not found"},
        )
    return request


def _get_request_by_id(request_id: UUID, db: Session) -> ReimbursementRequest:
    request = db.scalars(
        _request_detail_statement().where(ReimbursementRequest.id == request_id)
    ).first()
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REQUEST_NOT_FOUND", "message": "Reimbursement request not found"},
        )
    return request


def _ensure_request_visible(
    request: ReimbursementRequest,
    current_user: User,
    db: Session,
) -> None:
    if not user_can_transition_store_request(db, current_user, request.store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the request store",
            },
        )


def _mark_accounting_request_taken_if_needed(
    request: ReimbursementRequest,
    current_user: User,
    db: Session,
) -> ReimbursementRequest:
    summary = summarize_reimbursement_request(request)
    if not mark_accounting_request_taken_on_open(
        request,
        actor=current_user,
        summary=summary,
    ):
        return request

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="accounting_request_taken",
            from_status="single",
            to_status="taken",
            message="Accounting request opened by user.",
        )
    )
    db.commit()
    return _get_request_by_id(request.id, db)


def _current_open_period(db: Session) -> Period | None:
    today = datetime.now(UTC).date()
    period = db.scalar(
        select(Period)
        .where(
            Period.status == PeriodStatus.open,
            Period.starts_on <= today,
            Period.ends_on >= today,
        )
        .order_by(Period.starts_on.desc())
    )
    if period is not None:
        return period
    return db.scalar(
        select(Period)
        .where(Period.status == PeriodStatus.open)
        .order_by(Period.starts_on.desc())
    )


def _generate_request_folio(
    store: Store,
    db: Session,
) -> str:
    fecha_local = datetime.now(
        MEXICO_CITY_TZ
    ).date()

    prefix = (
        f"{_frontend_store_code(store)}-"
        f"{fecha_local:%d%m%Y}"
    )

    existing_folios = db.scalars(
        select(ReimbursementRequest.folio).where(
            ReimbursementRequest.folio.is_not(None),
            ReimbursementRequest.folio.like(
                f"{prefix}%"
            ),
        )
    )

    highest_sequence = 0

    for existing_folio in existing_folios:
        if (
            existing_folio is None
            or not existing_folio.startswith(prefix)
        ):
            continue

        suffix = existing_folio.removeprefix(
            prefix
        )

        if suffix.isdecimal():
            highest_sequence = max(
                highest_sequence,
                int(suffix),
            )

    return f"{prefix}{highest_sequence + 1}"


def _frontend_store_code(store: Store) -> str:
    candidate = store.code.removeprefix("HUD-")
    if len(candidate) == 4 and candidate.startswith("T") and candidate[1:].isdecimal():
        return candidate
    return store.code


def _request_is_visible_for_role(
    request: ReimbursementRequest,
    current_user: User,
    db: Session,
) -> bool:
    summary = summarize_reimbursement_request(request)
    pending_authorization_ids = set(summary.missing_authorization_expense_ids)
    has_pending_authorization = bool(pending_authorization_ids)

    if (
        current_user.role == UserRole.authorizer
        and request.status
        == ReimbursementRequestStatus.submitted
    ):
        return request_has_authorization_visible_to_user(
            request,
            current_user,
            db,
            pending_expense_ids=pending_authorization_ids,
        )

    if (
        current_user.role == UserRole.authorizer
        and request.status == ReimbursementRequestStatus.authorization_review
    ):
        if has_pending_authorization:
            return request_has_authorization_visible_to_user(
                request,
                current_user,
                db,
                pending_expense_ids=pending_authorization_ids,
            )
        return request_has_authorization_area_for_user(request, current_user, db)

    if request.status != ReimbursementRequestStatus.submitted:
        return True

    return True


def _frontend_role(role: UserRole) -> str:
    return ROLE_TO_FRONTEND[role]


def _frontend_request_status(status_value: ReimbursementRequestStatus) -> str:
    if status_value in {ReimbursementRequestStatus.paid, ReimbursementRequestStatus.closed}:
        return "Pagada"
    if status_value == ReimbursementRequestStatus.rejected:
        return "Rechazada"
    if status_value in {
        ReimbursementRequestStatus.direction_approved,
        ReimbursementRequestStatus.approved_for_payment,
    }:
        return "Aprobada"
    return "En revisión"


def _frontend_expense_status(status_value: ExpenseStatus) -> str:
    if status_value == ExpenseStatus.approved:
        return "Autorizado"
    if status_value == ExpenseStatus.rejected:
        return "No autorizado"
    if status_value == ExpenseStatus.removed:
        return "Eliminado"
    return "En revisión"


def _frontend_authorization_status(expense: Expense) -> str:
    if not expense.requires_authorization:
        return ""
    if expense.status == ExpenseStatus.rejected:
        return "no_autorizado"
    if expense.authorized_at is not None or expense.status == ExpenseStatus.approved:
        return "autorizado"
    return ""


def _request_display_date(request: ReimbursementRequest) -> date:
    timestamp = request.submitted_at or request.created_at
    return timestamp.date()


def _format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _parse_frontend_date(value: str | date | None, period: Period) -> date:
    if isinstance(value, date):
        return value
    if value:
        stripped = value.strip()
        for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(stripped, date_format).replace(tzinfo=UTC).date()
            except ValueError:
                continue
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_FRONTEND_DATE",
                "message": "Expense date must use YYYY-MM-DD, DD-MM-YYYY or DD/MM/YYYY",
            },
        )

    today = datetime.now(UTC).date()
    if period.starts_on <= today <= period.ends_on:
        return today
    return period.starts_on


def _expense_sort_key(expense: Expense) -> tuple[date, str]:
    return expense.spent_on, expense.merchant


def _invoice_count(expense: Expense) -> int:
    xml_count = sum(1 for attachment in expense.attachments if attachment.attachment_type == AttachmentType.cfdi_xml)
    if xml_count:
        return xml_count
    return 1 if expense.cfdi_uuid or _suggested_cfdi_uuid_from_ocr(expense) else 0


def _suggested_cfdi_uuid_from_ocr(expense: Expense) -> str | None:
    for attachment in sorted(expense.attachments, key=lambda item: item.uploaded_at):
        extraction = attachment.ocr_extraction
        if extraction is None:
            continue
        extraction_status = getattr(extraction.status, "value", extraction.status)
        if extraction_status != "succeeded":
            continue
        if extraction.suggested_cfdi_uuid:
            return extraction.suggested_cfdi_uuid.upper()
    return None


def _expense_document_urls(expense: Expense) -> dict[str, str | None]:
    attachments = sorted(expense.attachments, key=lambda item: item.uploaded_at)
    receipts = [
        attachment
        for attachment in attachments
        if attachment.attachment_type == AttachmentType.receipt
    ]
    other_files = [
        attachment
        for attachment in attachments
        if attachment.attachment_type == AttachmentType.other
    ]

    factura = _first_attachment(attachments, AttachmentType.cfdi_xml)
    if factura is None:
        factura = next((_ for _ in receipts if _looks_like_invoice(_)), None)

    vale = next((_ for _ in other_files if _looks_like_vale(_)), None)
    if vale is None:
        vale = next((_ for _ in receipts if _looks_like_vale(_)), None)
    if vale is None:
        vale = other_files[0] if other_files else None

    used_ids = {
        attachment.id
        for attachment in (factura, vale)
        if attachment is not None
    }
    recibo = next(
        (
            attachment
            for attachment in receipts
            if attachment.id not in used_ids and _looks_like_receipt(attachment)
        ),
        None,
    )
    if recibo is None:
        recibo = next(
            (attachment for attachment in receipts if attachment.id not in used_ids),
            None,
        )

    return {
        "url_factura": _attachment_download_url(factura),
        "url_vale": _attachment_download_url(vale),
        "url_recibo": _attachment_download_url(recibo),
    }


def _first_attachment(
    attachments: list[Attachment],
    attachment_type: AttachmentType,
) -> Attachment | None:
    return next(
        (
            attachment
            for attachment in attachments
            if attachment.attachment_type == attachment_type
        ),
        None,
    )


def _attachment_download_url(attachment: Attachment | None) -> str | None:
    if attachment is None:
        return None
    return f"/api/v1/attachments/{attachment.id}/download/me"


def _latest_reembolso_attachment(request: ReimbursementRequest) -> Attachment | None:
    return next(
        (
            attachment
            for attachment in sorted(
                request.attachments,
                key=lambda item: item.uploaded_at,
                reverse=True,
            )
            if attachment.attachment_type == AttachmentType.cash_box_format
        ),
        None,
    )


def _looks_like_invoice(attachment: Attachment) -> bool:
    extraction = attachment.ocr_extraction
    if extraction is not None and extraction.suggested_cfdi_uuid:
        return True
    return _filename_has_any(attachment, {"factura", "invoice", "cfdi", "xml"})


def _looks_like_vale(attachment: Attachment) -> bool:
    return _filename_has_any(attachment, {"vale"})


def _looks_like_receipt(attachment: Attachment) -> bool:
    return _filename_has_any(attachment, {"recibo", "ticket", "comprobante", "receipt"})


def _filename_has_any(attachment: Attachment, terms: set[str]) -> bool:
    filename = (attachment.filename or "").lower()
    return any(term in filename for term in terms)


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _money_or_none(value: Decimal | None) -> Decimal | None:
    return _money(value) if value is not None else None


def _rate_or_none(value: Decimal | None) -> Decimal | None:
    return Decimal(value).quantize(Decimal("0.01")) if value is not None else None


def _float_or_none(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
