from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
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
from app.schemas.audit_log import AuditLogRead, FrontendAuditLogRead
from app.schemas.frontend import (
    FrontendCaptureCreate,
    FrontendCaptureEventCreate,
    FrontendClickAuditCreate,
    FrontendContextRead,
    FrontendExpensePartitionCreate,
    FrontendGastoCreate,
    FrontendGastoRead,
    FrontendManagementMonthlyProductivityRowRead,
    FrontendManagementProductivityDashboardRead,
    FrontendManagementProductivityRowRead,
    FrontendObservationCreate,
    FrontendProductivityActionRead,
    FrontendRoleMonthlyProductivityRowRead,
    FrontendRoleProductivityDashboardRead,
    FrontendRoleProductivityRowRead,
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
    authorizer_has_global_authorization_area,
    expense_is_visible_to_authorizer,
    get_or_create_authorization_area,
    request_has_authorization_area_for_user,
    request_has_authorization_visible_to_user,
)
from app.services.expense_authorization_rules import (
    category_requires_manual_authorization_area,
    resolve_expense_authorization,
)
from app.services.expense_capture_audit import (
    CAPTURE_STARTED,
    add_capture_event,
    capture_event_message,
    get_capture,
    link_capture_to_expense,
)
from app.services.frontend_actions import ACTION_LABELS, available_actions_for_request
from app.services.permissions import user_can_transition_store_request, user_has_store_assignment
from app.services.reimbursement_periods import (
    ExpenseOutsideReimbursementPeriod,
    ReimbursementPeriodBoundaryUnavailable,
    actualizar_fecha_fin_reembolso,
    obtener_contexto_periodo_reembolso,
    validate_expense_date_for_reimbursement,
)
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.tax_rules import (
    determinar_indice_iva_manual,
    determinar_tasa_iva_para_gasto,
    normalizar_texto,
)

router = APIRouter()
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
    UserRole.accountant,
    UserRole.accounting_manager,
    UserRole.treasury,
    UserRole.director,
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
    if _should_scope_queue_to_assigned_stores(current_user, db):
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
    week_start: Annotated[date | None, Query()] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> FrontendManagementProductivityDashboardRead:
    if current_user.role not in {UserRole.accounting_manager, UserRole.director, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only management users can view the productivity dashboard",
            },
        )

    day_labels = ["Lu", "Ma", "Mi", "Ju", "Vi"]
    today = datetime.now(MEXICO_CITY_TZ).date()
    selected_week_start = (week_start or today) - timedelta(
        days=(week_start or today).weekday()
    )
    selected_month = month or today.month
    selected_year = year or today.year
    week_end = selected_week_start + timedelta(days=4)
    window_start = datetime.combine(selected_week_start, time.min, tzinfo=MEXICO_CITY_TZ)
    window_end = datetime.combine(
        selected_week_start + timedelta(days=7),
        time.min,
        tzinfo=MEXICO_CITY_TZ,
    )
    month_start = date(selected_year, selected_month, 1)
    if selected_month == 12:
        next_month_start = date(selected_year + 1, 1, 1)
    else:
        next_month_start = date(selected_year, selected_month + 1, 1)
    month_window_start = datetime.combine(month_start, time.min, tzinfo=MEXICO_CITY_TZ)
    month_window_end = datetime.combine(next_month_start, time.min, tzinfo=MEXICO_CITY_TZ)

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
    monthly_totals_by_accountant = {
        accountant.id: 0
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

    monthly_event_rows = db.execute(
        select(AuditLog.actor_user_id)
        .join(User, AuditLog.actor_user_id == User.id)
        .where(
            AuditLog.action == "request_status_changed",
            AuditLog.to_status == ReimbursementRequestStatus.accounting_reviewed.value,
            AuditLog.created_at >= month_window_start,
            AuditLog.created_at < month_window_end,
            User.role == UserRole.accountant,
        )
    )

    for (accountant_id,) in monthly_event_rows:
        if accountant_id not in monthly_totals_by_accountant:
            continue
        monthly_totals_by_accountant[accountant_id] += 1

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
    monthly_rows = [
        FrontendManagementMonthlyProductivityRowRead(
            accountant_id=accountant.id,
            accountant_name=accountant.full_name,
            total=monthly_totals_by_accountant[accountant.id],
        )
        for accountant in accountants
    ]

    return FrontendManagementProductivityDashboardRead(
        week_starts_on=selected_week_start,
        week_ends_on=week_end,
        month=selected_month,
        year=selected_year,
        days=day_labels,
        rows=rows,
        totals=totals,
        grand_total=sum(totals.values()),
        monthly_rows=monthly_rows,
        monthly_grand_total=sum(row.total for row in monthly_rows),
    )


@dataclass(frozen=True)
class _ProductivityAction:
    key: str
    label: str
    audit_action: str
    to_status: ReimbursementRequestStatus | None = None


MANAGER_PRODUCTIVITY_ACTIONS = (
    _ProductivityAction(
        key="send_to_treasury",
        label="Enviadas a tesorería",
        audit_action="request_status_changed",
        to_status=ReimbursementRequestStatus.accounting_manager_approved,
    ),
    _ProductivityAction(
        key="confirm_payment",
        label="Pagos confirmados",
        audit_action="payment_recorded",
    ),
)
TREASURY_PRODUCTIVITY_ACTIONS = (
    _ProductivityAction(
        key="approve_payment",
        label="Pagos aprobados",
        audit_action="request_status_changed",
        to_status=ReimbursementRequestStatus.direction_approved,
    ),
)


@router.get(
    "/gerencia/productividad/gerentes/me",
    response_model=FrontendRoleProductivityDashboardRead,
)
def get_managers_productivity_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    week_start: Annotated[date | None, Query()] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> FrontendRoleProductivityDashboardRead:
    _ensure_productivity_viewer(current_user)
    return _build_role_productivity_dashboard(
        db,
        role=UserRole.accounting_manager,
        actions=MANAGER_PRODUCTIVITY_ACTIONS,
        week_start=week_start,
        month=month,
        year=year,
    )


@router.get(
    "/gerencia/productividad/tesoreros/me",
    response_model=FrontendRoleProductivityDashboardRead,
)
def get_treasurers_productivity_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    week_start: Annotated[date | None, Query()] = None,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    year: Annotated[int | None, Query(ge=2020, le=2100)] = None,
) -> FrontendRoleProductivityDashboardRead:
    _ensure_productivity_viewer(current_user)
    return _build_role_productivity_dashboard(
        db,
        role=UserRole.treasury,
        actions=TREASURY_PRODUCTIVITY_ACTIONS,
        week_start=week_start,
        month=month,
        year=year,
    )


def _ensure_productivity_viewer(current_user: User) -> None:
    if current_user.role not in {UserRole.director, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Only direction users can view this productivity dashboard",
            },
        )


def _build_role_productivity_dashboard(
    db: Session,
    *,
    role: UserRole,
    actions: tuple[_ProductivityAction, ...],
    week_start: date | None,
    month: int | None,
    year: int | None,
) -> FrontendRoleProductivityDashboardRead:
    day_labels = ["Lu", "Ma", "Mi", "Ju", "Vi"]
    today = datetime.now(MEXICO_CITY_TZ).date()
    selected_week_start = (week_start or today) - timedelta(
        days=(week_start or today).weekday()
    )
    selected_week_end = selected_week_start + timedelta(days=4)
    selected_month = month or today.month
    selected_year = year or today.year

    users = list(
        db.scalars(
            select(User)
            .where(User.role == role, User.is_active.is_(True))
            .order_by(User.full_name)
        )
    )
    weekly_values = {
        (user.id, action.key): {day: 0 for day in day_labels}
        for user in users
        for action in actions
    }
    monthly_totals = {
        (user.id, action.key): 0
        for user in users
        for action in actions
    }

    for action in actions:
        # Una solicitud cuenta una sola vez por usuario y acción: se conserva el primer evento.
        statement = (
            select(AuditLog.actor_user_id, func.min(AuditLog.created_at))
            .join(User, AuditLog.actor_user_id == User.id)
            .where(
                AuditLog.action == action.audit_action,
                AuditLog.reimbursement_request_id.is_not(None),
                User.role == role,
            )
            .group_by(AuditLog.reimbursement_request_id, AuditLog.actor_user_id)
        )
        if action.to_status is not None:
            statement = statement.where(AuditLog.to_status == action.to_status.value)

        for user_id, first_event_at in db.execute(statement):
            if (user_id, action.key) not in monthly_totals:
                continue
            if first_event_at.tzinfo is None:
                first_event_at = first_event_at.replace(tzinfo=UTC)
            local_event_at = first_event_at.astimezone(MEXICO_CITY_TZ)
            local_date = local_event_at.date()

            if local_date.year == selected_year and local_date.month == selected_month:
                monthly_totals[(user_id, action.key)] += 1
            if selected_week_start <= local_date <= selected_week_end:
                weekly_values[(user_id, action.key)][day_labels[local_date.weekday()]] += 1

    totals = {day: 0 for day in day_labels}
    totals_by_action = {action.key: {day: 0 for day in day_labels} for action in actions}
    rows: list[FrontendRoleProductivityRowRead] = []
    monthly_rows: list[FrontendRoleMonthlyProductivityRowRead] = []
    for user in users:
        for action in actions:
            values = weekly_values[(user.id, action.key)]
            for day, value in values.items():
                totals[day] += value
                totals_by_action[action.key][day] += value
            rows.append(
                FrontendRoleProductivityRowRead(
                    user_id=user.id,
                    user_name=user.full_name,
                    action_key=action.key,
                    action_label=action.label,
                    values=values,
                    total=sum(values.values()),
                )
            )
            monthly_rows.append(
                FrontendRoleMonthlyProductivityRowRead(
                    user_id=user.id,
                    user_name=user.full_name,
                    action_key=action.key,
                    action_label=action.label,
                    total=monthly_totals[(user.id, action.key)],
                )
            )

    return FrontendRoleProductivityDashboardRead(
        week_starts_on=selected_week_start,
        week_ends_on=selected_week_end,
        month=selected_month,
        year=selected_year,
        days=day_labels,
        actions=[
            FrontendProductivityActionRead(key=action.key, label=action.label)
            for action in actions
        ],
        rows=rows,
        totals=totals,
        totals_by_action=totals_by_action,
        grand_total=sum(totals.values()),
        monthly_rows=monthly_rows,
        monthly_grand_total=sum(row.total for row in monthly_rows),
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

    try:
        contexto_periodo = (
            obtener_contexto_periodo_reembolso(
                db=db,
                store_id=store.id,
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

        reimbursement_ends_on=None,

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
    audit_base_time = datetime.now(UTC)
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="request_created_from_frontend",
            to_status=request.status.value,
            message="Reimbursement request created from frontend-compatible API.",
            created_at=audit_base_time,
        )
    )

    expense_count = len(request_in.gastos)
    for expense_index, expense_in in enumerate(request_in.gastos, start=1):
        expense = _expense_from_frontend(expense_in, request=request, period=period, db=db)
        db.add(expense)
        db.flush()
        link_capture_to_expense(db, expense_in.capture_id, current_user, request, expense)
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
                message=_expense_created_message(expense),
                event_payload=_expense_created_payload(
                    expense,
                    expense_sequence=expense_index,
                    expense_count=expense_count,
                ),
                created_at=audit_base_time + timedelta(microseconds=expense_index),
            )
        )

    actualizar_fecha_fin_reembolso(db, request)

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
    actualizar_fecha_fin_reembolso(db, request)
    link_capture_to_expense(db, expense_in.capture_id, current_user, request, expense)
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
    _add_frontend_button_selected_audit_event(
        db,
        request=request,
        actor=current_user,
        action_key="add_expense",
        expense=expense,
        authenticated=True,
    )
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="expense_created_from_frontend",
            message=_expense_created_message(expense),
            event_payload=_expense_created_payload(expense),
        )
    )
    db.commit()
    db.expire_all()
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

    previous_expense_status = expense.status
    deleted_expense_payload = {
        "expense_id": str(expense.id),
        "expense_name": _expense_display_name(expense),
        "merchant": expense.merchant,
        "amount": str(_money(expense.amount)),
        "category": expense.category,
    }
    removal_reason = f"Gasto eliminado por tienda: {_expense_display_name(expense)}."
    request.reported_total = _active_frontend_expense_total(
        request,
        excluding_expense_id=expense.id,
    )
    _add_frontend_button_selected_audit_event(
        db,
        request=request,
        actor=current_user,
        action_key="remove_expense",
        expense=expense,
        authenticated=True,
    )
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="expense_removed_from_request",
            message=removal_reason,
            event_payload={
                "actor_role": current_user.role.value,
                "request_status": request.status.value,
                "previous_expense_status": previous_expense_status.value,
                "reported_total": str(request.reported_total),
                "authenticated": True,
                "draft_delete": True,
                "hard_delete": True,
                **deleted_expense_payload,
            },
        )
    )
    db.delete(expense)
    actualizar_fecha_fin_reembolso(db, request)

    db.commit()
    db.expire_all()
    request = _get_request_by_id(request.id, db)
    return _request_payload(request, current_user, db)


@router.post(
    "/solicitudes/{request_identifier}/gastos/{expense_id}/particiones/me",
    response_model=FrontendSolicitudRead,
)
def partition_frontend_expense(
    request_identifier: str,
    expense_id: UUID,
    partition_in: FrontendExpensePartitionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendSolicitudRead:
    request = _get_request_by_frontend_identifier(request_identifier, db)
    _ensure_request_visible(request, current_user, db)
    _ensure_partition_allowed(request, current_user)
    expense = _expense_in_request_or_404(request, expense_id)
    _ensure_expense_can_be_partitioned(expense)

    total_original = _money(expense.amount)
    total_particiones = sum(
        (_money(partition.monto) for partition in partition_in.particiones),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    if abs(total_original - total_particiones) > Decimal("0.01"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "PARTITION_TOTAL_MISMATCH",
                "message": "La suma de las particiones debe ser igual al total del gasto.",
            },
        )

    active_children = _active_partition_children(expense)
    previous_partitions = [_partition_audit_item(child) for child in active_children]

    now = datetime.now(UTC)
    for child in active_children:
        child.status = ExpenseStatus.removed
        child.removed_at = now
        child.removed_by_user_id = current_user.id
        child.removal_reason = "Partición reemplazada."

    partition_count = len(partition_in.particiones)
    created_children: list[Expense] = []
    for index, partition in enumerate(partition_in.particiones, start=1):
        amount = _money(partition.monto)
        tax_rate = _rate_or_none(partition.impuesto) or Decimal("0.00")
        tax_amount, tax_subtotal = _tax_amounts_from_rate(amount, tax_rate)
        child = Expense(
            reimbursement_request_id=request.id,
            period_id=expense.period_id,
            partition_parent_expense_id=expense.id,
            partition_index=index,
            partition_count=partition_count,
            merchant=f"Partición {index}/{partition_count} - {partition.categoria}",
            amount=amount,
            currency=expense.currency,
            spent_on=expense.spent_on,
            category=partition.categoria.strip(),
            description=f"Partición {index}/{partition_count} del gasto {expense.merchant}.",
            supplier_tax_id=expense.supplier_tax_id,
            requires_authorization=expense.requires_authorization,
            authorization_area_id=expense.authorization_area_id,
            authorized_at=expense.authorized_at,
            authorized_by_user_id=expense.authorized_by_user_id,
            authorization_note=expense.authorization_note,
            status=expense.status,
            cfdi_issuer_rfc=expense.cfdi_issuer_rfc,
            cfdi_receiver_rfc=expense.cfdi_receiver_rfc,
            cfdi_subtotal=tax_subtotal,
            cfdi_total=amount,
            cfdi_currency=expense.cfdi_currency or expense.currency,
            cfdi_tax_amount=tax_amount,
            cfdi_tax_rate=tax_rate,
            sap_tax_index_override=determinar_indice_iva_manual(tax_rate),
        )
        db.add(child)
        db.flush()
        created_children.append(child)

    new_partitions = [_partition_audit_item(child) for child in created_children]
    partition_action = (
        "expense_partition_updated"
        if previous_partitions
        else "expense_partitioned"
    )
    partition_message = (
        _partition_updated_message(
            expense=expense,
            original_amount=total_original,
            previous_partitions=previous_partitions,
            new_partitions=new_partitions,
        )
        if previous_partitions
        else _partition_created_message(
            expense=expense,
            original_amount=total_original,
            partitions=new_partitions,
        )
    )

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action=partition_action,
            message=partition_message,
            event_payload={
                "actor_role": current_user.role.value,
                "request_status": request.status.value,
                "parent_expense_id": str(expense.id),
                "parent_expense_name": _expense_display_name(expense),
                "partition_count": partition_count,
                "original_amount": str(total_original),
                "partition_total": str(total_particiones),
                "previous_partitions": previous_partitions,
                "partitions": new_partitions,
            },
        )
    )
    db.commit()
    db.expire_all()
    request = _get_request_by_id(request.id, db)
    return _request_payload(request, current_user, db)


@router.delete(
    "/solicitudes/{request_identifier}/gastos/{expense_id}/particiones/me",
    response_model=FrontendSolicitudRead,
)
def cancel_frontend_expense_partition(
    request_identifier: str,
    expense_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendSolicitudRead:
    request = _get_request_by_frontend_identifier(request_identifier, db)
    _ensure_request_visible(request, current_user, db)
    _ensure_partition_allowed(request, current_user)
    expense = _expense_in_request_or_404(request, expense_id)
    if expense.partition_parent_expense_id is not None:
        expense = _expense_in_request_or_404(request, expense.partition_parent_expense_id)

    active_children = _active_partition_children(expense)
    if not active_children:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXPENSE_NOT_PARTITIONED",
                "message": "El gasto no tiene particiones activas.",
            },
        )

    now = datetime.now(UTC)
    cancelled_partitions = [_partition_audit_item(child) for child in active_children]
    for child in active_children:
        child.status = ExpenseStatus.removed
        child.removed_at = now
        child.removed_by_user_id = current_user.id
        child.removal_reason = "Partición anulada."

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id,
            actor_user_id=current_user.id,
            actor_type=AuditActorType.user,
            action="expense_partition_cancelled",
            message=_partition_cancelled_message(
                expense=expense,
                original_amount=_money(expense.amount),
                partitions=cancelled_partitions,
            ),
            event_payload={
                "actor_role": current_user.role.value,
                "request_status": request.status.value,
                "parent_expense_id": str(expense.id),
                "parent_expense_name": _expense_display_name(expense),
                "partition_count": len(active_children),
                "cancelled_expense_ids": [str(child.id) for child in active_children],
                "cancelled_partitions": cancelled_partitions,
            },
        )
    )
    db.commit()
    db.expire_all()
    request = _get_request_by_id(request.id, db)
    return _request_payload(request, current_user, db)


@router.post("/capturas/me", response_model=AuditLogRead, status_code=201)
def start_expense_capture(
    capture_in: FrontendCaptureCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditLog:
    if current_user.role not in {UserRole.store, UserRole.admin}:
        raise HTTPException(status_code=403, detail="Solo tienda o admin pueden capturar gastos.")
    if db.get(AuditLog, capture_in.capture_id) is not None:
        return get_capture(db, capture_in.capture_id, current_user, require_open=False)
    request = None
    if capture_in.request_id:
        request = _get_request_by_id(capture_in.request_id, db)
        _ensure_request_visible(request, current_user, db)
        if request.status not in {
            ReimbursementRequestStatus.draft, ReimbursementRequestStatus.correction_required,
        }:
            raise HTTPException(status_code=409, detail="La solicitud ya no permite añadir gastos.")
        store = request.store
    else:
        stores = _stores_for_user(current_user, db)
        if not stores:
            raise HTTPException(status_code=403, detail="No tienes una tienda asignada para capturar.")
        store = stores[0]
    capture = AuditLog(
        id=capture_in.capture_id,
        reimbursement_request_id=request.id if request else None,
        actor_user_id=current_user.id,
        actor_type=AuditActorType.user,
        action=CAPTURE_STARTED,
        message="Captura de gasto iniciada, todavía no añadida a la solicitud.",
        event_payload={
            "capture_id": str(capture_in.capture_id), "store_id": str(store.id),
            "store_code": _frontend_store_code(store), "actor_role": current_user.role.value,
            "actor_name": current_user.full_name, "category": capture_in.category,
            "document_type": capture_in.document_type,
        },
        created_at=datetime.now(UTC),
    )
    db.add(capture)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return get_capture(db, capture_in.capture_id, current_user, require_open=False)
    return capture


@router.post("/capturas/{capture_id}/eventos/me", response_model=AuditLogRead, status_code=201)
def record_expense_capture_event(
    capture_id: UUID,
    event_in: FrontendCaptureEventCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditLog:
    capture = get_capture(db, capture_id, current_user, require_open=False)
    existing = db.get(AuditLog, event_in.event_id)
    if existing:
        if (existing.event_payload or {}).get("capture_id") != str(capture_id) or (
            existing.actor_user_id != current_user.id or existing.id == capture.id
        ):
            raise HTTPException(status_code=409, detail="El identificador del movimiento ya existe.")
        return existing
    get_capture(db, capture_id, current_user)
    event = add_capture_event(
        db, capture, current_user,
        action=f"expense_capture_{event_in.action}", message=capture_event_message(event_in),
        payload={**event_in.model_dump(exclude={"event_id", "action"}), "source": "frontend"},
        event_id=event_in.event_id,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.get(AuditLog, event_in.event_id)
        if existing is None or existing.actor_user_id != current_user.id or (
            (existing.event_payload or {}).get("capture_id") != str(capture_id)
        ):
            raise HTTPException(status_code=409, detail="El identificador del movimiento ya existe.") from exc
        return existing
    return event


@router.get("/audit-events/me", response_model=list[FrontendAuditLogRead])
def list_frontend_audit_events(
    day: date,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    utc_offset_minutes: Annotated[int, Query(ge=-840, le=840)] = -360,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[FrontendAuditLogRead]:
    starts_at = datetime.combine(day, time.min, timezone(timedelta(minutes=utc_offset_minutes)))
    statement = (
        select(AuditLog, ReimbursementRequest, Store, User)
        .outerjoin(ReimbursementRequest, AuditLog.reimbursement_request_id == ReimbursementRequest.id)
        .outerjoin(Store, ReimbursementRequest.store_id == Store.id)
        .outerjoin(User, AuditLog.actor_user_id == User.id)
        .where(
            AuditLog.created_at >= starts_at.astimezone(UTC),
            AuditLog.created_at < (starts_at + timedelta(days=1)).astimezone(UTC),
        )
    )
    if current_user.role in {UserRole.store, UserRole.authorizer}:
        store_ids = [store.id for store in _stores_for_user(current_user, db)]
        statement = statement.where(or_(
            ReimbursementRequest.store_id.in_(store_ids),
            and_(
                AuditLog.reimbursement_request_id.is_(None),
                AuditLog.event_payload["store_id"].as_string().in_([str(s) for s in store_ids]),
            ),
        ))
    results = db.execute(statement.order_by(
        AuditLog.created_at.desc(), AuditLog.id.desc()
    ).limit(limit).offset(offset))
    return [
        FrontendAuditLogRead(
            **AuditLogRead.model_validate(event).model_dump(),
            store_code=_frontend_store_code(store) if store else (event.event_payload or {}).get("store_code"),
            request_folio=request.folio if request else None,
            actor_name=actor.full_name if actor else (event.event_payload or {}).get("actor_name"),
            actor_role=actor.role.value if actor else (event.event_payload or {}).get("actor_role"),
        )
        for event, request, store, actor in results
    ]


@router.post(
    "/solicitudes/{request_identifier}/clicks/me",
    response_model=AuditLogRead,
    status_code=status.HTTP_201_CREATED,
)
def record_frontend_click(
    request_identifier: str,
    click_in: FrontendClickAuditCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuditLog:
    request = _get_request_by_frontend_identifier(request_identifier, db)
    _ensure_request_visible(request, current_user, db)

    expense_id = None
    if click_in.expense_id and any(expense.id == click_in.expense_id for expense in request.expenses):
        expense_id = click_in.expense_id

    button_label = click_in.button_label.strip()
    audit_event = AuditLog(
        reimbursement_request_id=request.id,
        expense_id=expense_id,
        actor_user_id=current_user.id,
        actor_type=AuditActorType.user,
        action="ui_click",
        message=f"Click registrado: {button_label}.",
        event_payload={
            "actor_role": current_user.role.value,
            "button_label": button_label,
            "page_path": click_in.page_path,
            "element_type": click_in.element_type,
            "action_key": click_in.action_key,
            "expense_id": str(expense_id) if expense_id else None,
            "request_status": request.status.value,
            "authenticated": True,
        },
    )
    db.add(audit_event)
    db.commit()
    db.refresh(audit_event)
    return audit_event


def _active_frontend_expense_total(
    request: ReimbursementRequest,
    *,
    excluding_expense_id: UUID | None = None,
) -> Decimal:
    return _money(
        sum(
            (
                expense.amount
                for expense in request.expenses
                if expense.id != excluding_expense_id
                if expense.status not in {ExpenseStatus.removed, ExpenseStatus.rejected}
                and expense.removed_at is None
            ),
            Decimal("0.00"),
        )
    )


def _expense_display_name(expense: Expense) -> str:
    return f"Gasto - {expense.category or 'Gasto General'}"


def _expense_created_message(expense: Expense) -> str:
    return f"Expense created for {_expense_display_name(expense)}."


def _expense_created_payload(
    expense: Expense,
    *,
    expense_sequence: int | None = None,
    expense_count: int | None = None,
) -> dict[str, str]:
    payload = {
        "expense_name": _expense_display_name(expense),
        "merchant": expense.merchant,
        "amount": str(_money(expense.amount)),
        "currency": expense.currency,
        "category": expense.category or "Gasto General",
        "spent_on": expense.spent_on.isoformat(),
    }
    if expense_sequence is not None:
        payload["expense_sequence"] = str(expense_sequence)
    if expense_count is not None:
        payload["expense_count"] = str(expense_count)
    return payload


def _add_frontend_button_selected_audit_event(
    db: Session,
    *,
    request: ReimbursementRequest,
    actor: User,
    action_key: str,
    authenticated: bool,
    expense: Expense | None = None,
) -> None:
    button_label = ACTION_LABELS.get(action_key, action_key)
    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            expense_id=expense.id if expense else None,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="button_selected",
            message=f"Botón seleccionado: {button_label}.",
            event_payload={
                "action_key": action_key,
                "button_label": button_label,
                "request_status": request.status.value,
                "expense_id": str(expense.id) if expense else None,
                "authenticated": authenticated,
            },
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
        selectinload(ReimbursementRequest.expenses).selectinload(Expense.partition_children),
        selectinload(ReimbursementRequest.expenses)
        .selectinload(Expense.partition_parent)
        .selectinload(Expense.attachments)
        .selectinload(Attachment.ocr_extraction),
        selectinload(ReimbursementRequest.expenses)
        .selectinload(Expense.partition_parent)
        .selectinload(Expense.cfdi_validations),
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
                _frontend_visible_expenses(
                    request.expenses,
                    current_user,
                    db,
                    store_id=request.store_id,
                ),
                key=_expense_sort_key,
            )
        ],
        monto_total=float(calculated_total),
        reported_total=float(reported_total) if reported_total is not None else None,
        calculated_total=float(calculated_total),
        expense_count=summary.expense_count,
        authorization_pending_count=len(summary.missing_authorization_expense_ids),
        ready_for_authorization_approval=summary.ready_for_authorization_approval,
        reembolso_attachment_id=reembolso_attachment.id if reembolso_attachment else None,
        reembolso_file_name=reembolso_attachment.filename if reembolso_attachment else None,
        reembolso_download_url=_attachment_download_url(reembolso_attachment),
        available_actions=actions,
        action_labels={action: ACTION_LABELS.get(action, action) for action in actions},
    )


def _ensure_partition_allowed(request: ReimbursementRequest, current_user: User) -> None:
    if current_user.role not in {UserRole.accountant, UserRole.admin}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN_ROLE",
                "message": "Solo contabilidad o admin pueden particionar gastos.",
            },
        )
    if request.status not in {
        ReimbursementRequestStatus.under_accounting_review,
        ReimbursementRequestStatus.accounting_reviewed,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_IN_ACCOUNTING_REVIEW",
                "message": "El gasto solo puede particionarse durante revisión contable.",
            },
        )


def _expense_in_request_or_404(request: ReimbursementRequest, expense_id: UUID) -> Expense:
    expense = next((item for item in request.expenses if item.id == expense_id), None)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
    return expense


def _ensure_expense_can_be_partitioned(expense: Expense) -> None:
    if expense.partition_parent_expense_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "PARTITION_CHILD_CANNOT_BE_PARTITIONED",
                "message": "Una partición no puede particionarse nuevamente.",
            },
        )
    if not _expense_is_active(expense):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EXPENSE_EXCLUDED",
                "message": "Los gastos eliminados o rechazados no pueden particionarse.",
            },
        )


def _expense_is_active(expense: Expense) -> bool:
    return (
        expense.status not in {ExpenseStatus.removed, ExpenseStatus.rejected}
        and expense.removed_at is None
    )


def _active_partition_children(expense: Expense) -> list[Expense]:
    return [
        child
        for child in expense.partition_children
        if _expense_is_active(child)
    ]


def _has_active_partition_children(expense: Expense) -> bool:
    return bool(_active_partition_children(expense))


def _partition_audit_item(expense: Expense) -> dict[str, str | int | None]:
    return {
        "expense_id": str(expense.id),
        "index": expense.partition_index,
        "count": expense.partition_count,
        "category": expense.category or "Gasto General",
        "amount": str(_money(expense.amount)),
        "cfdi_tax_rate": str(_rate_or_none(expense.cfdi_tax_rate) or Decimal("0.00")),
    }


def _partition_created_message(
    *,
    expense: Expense,
    original_amount: Decimal,
    partitions: list[dict[str, str | int | None]],
) -> str:
    header = (
        f"Partición creada sobre {_expense_display_name(expense)}, "
        f"Monto - {_format_money_for_audit(original_amount)}, "
        f"Particiones - {len(partitions)}"
    )
    return "\n".join([header, *[_partition_line(partition) for partition in partitions]])


def _partition_updated_message(
    *,
    expense: Expense,
    original_amount: Decimal,
    previous_partitions: list[dict[str, str | int | None]],
    new_partitions: list[dict[str, str | int | None]],
) -> str:
    header = (
        f"Partición editada sobre {_expense_display_name(expense)}, "
        f"Monto - {_format_money_for_audit(original_amount)}, "
        f"Particiones - {len(new_partitions)}"
    )
    changes = _partition_change_lines(previous_partitions, new_partitions)
    if changes:
        return "\n".join([header, *changes])
    return "\n".join([header, *[_partition_line(partition) for partition in new_partitions]])


def _partition_cancelled_message(
    *,
    expense: Expense,
    original_amount: Decimal,
    partitions: list[dict[str, str | int | None]],
) -> str:
    header = (
        f"Partición anulada sobre {_expense_display_name(expense)}, "
        f"Monto - {_format_money_for_audit(original_amount)}. "
        f"Se anularon {len(partitions)} particiones:"
    )
    return "\n".join([header, *[_partition_line(partition) for partition in partitions]])


def _partition_change_lines(
    previous_partitions: list[dict[str, str | int | None]],
    new_partitions: list[dict[str, str | int | None]],
) -> list[str]:
    previous_by_index = {
        partition.get("index"): partition
        for partition in previous_partitions
    }
    lines: list[str] = []
    for new_partition in new_partitions:
        index = new_partition.get("index")
        previous_partition = previous_by_index.get(index)
        if previous_partition is None:
            lines.append(f"{_partition_label(new_partition)} creada: {_partition_summary(new_partition)}.")
            continue

        changes = _partition_field_changes(previous_partition, new_partition)
        if changes:
            lines.append(f"{_partition_label(new_partition)} cambió: {'; '.join(changes)}.")
    return lines


def _partition_field_changes(
    previous_partition: dict[str, str | int | None],
    new_partition: dict[str, str | int | None],
) -> list[str]:
    changes: list[str] = []
    previous_category = str(previous_partition.get("category") or "")
    new_category = str(new_partition.get("category") or "")
    if normalizar_texto(previous_category) != normalizar_texto(new_category):
        changes.append(f"categoría de {previous_category} a {new_category}")

    previous_amount = _money(previous_partition.get("amount"))
    new_amount = _money(new_partition.get("amount"))
    if previous_amount != new_amount:
        changes.append(
            "monto de "
            f"{_format_money_for_audit(previous_amount)} "
            f"a {_format_money_for_audit(new_amount)}"
        )

    previous_rate = _rate_or_none(previous_partition.get("cfdi_tax_rate")) or Decimal("0.00")
    new_rate = _rate_or_none(new_partition.get("cfdi_tax_rate")) or Decimal("0.00")
    if previous_rate != new_rate:
        changes.append(
            "impuesto de "
            f"{_format_tax_rate_for_audit(previous_rate)} "
            f"a {_format_tax_rate_for_audit(new_rate)}"
        )
    return changes


def _partition_line(partition: dict[str, str | int | None]) -> str:
    return f"{_partition_label(partition)}: {_partition_summary(partition)}."


def _partition_label(partition: dict[str, str | int | None]) -> str:
    index = partition.get("index") or "?"
    count = partition.get("count") or "?"
    return f"{index}/{count}"


def _partition_summary(partition: dict[str, str | int | None]) -> str:
    return (
        f"Categoría - {partition.get('category') or 'Gasto General'}, "
        f"Monto - {_format_money_for_audit(_money(partition.get('amount')))}, "
        "Impuesto - "
        f"{_format_tax_rate_for_audit(_rate_or_none(partition.get('cfdi_tax_rate')) or Decimal('0.00'))}"
    )


def _format_money_for_audit(amount: Decimal) -> str:
    return f"${_money(amount):,.2f}"


def _format_tax_rate_for_audit(rate: Decimal) -> str:
    normalized = rate.quantize(Decimal("0.01")).normalize()
    return f"{normalized}%"


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
    *,
    store_id: UUID,
) -> list[Expense]:
    return [
        expense
        for expense in expenses
        if _include_expense_in_frontend_payload(expense)
        if expense_is_visible_to_authorizer(
            db,
            current_user,
            expense,
            store_id=store_id,
        )
    ]


def _include_expense_in_frontend_payload(expense: Expense) -> bool:
    if expense.partition_parent_expense_id is None:
        return True
    return _expense_is_active(expense)


def _expense_payload(expense: Expense) -> FrontendGastoRead:
    category = expense.category or "Gasto General"
    evidence_expense = _expense_evidence_source(expense)
    folio = (
        expense.cfdi_uuid
        or evidence_expense.cfdi_uuid
        or _suggested_cfdi_uuid_from_ocr(evidence_expense)
        or "N/A"
    )
    document_urls = _expense_document_urls(evidence_expense)
    is_partition_child = expense.partition_parent_expense_id is not None
    has_partition_children = _has_active_partition_children(expense)
    partition_index = expense.partition_index if is_partition_child else None
    partition_count = expense.partition_count if is_partition_child else None
    return FrontendGastoRead(
        id=str(expense.id),
        backend_id=expense.id,
        nombre=(
            f"Partición {partition_index} / {partition_count} - {category}"
            if is_partition_child and partition_index and partition_count
            else f"Gasto - {category}"
        ),
        fecha=expense.spent_on,
        monto=float(_money(expense.amount)),
        tipo=category,
        type=category,
        folio=folio,
        folio_fiscal=expense.cfdi_uuid or evidence_expense.cfdi_uuid,
        observaciones=expense.description or "",
        cfdi_subtotal=_float_or_none(expense.cfdi_subtotal),
        cfdi_total=_float_or_none(expense.cfdi_total),
        cfdi_tax_amount=_float_or_none(expense.cfdi_tax_amount),
        cfdi_tax_rate=_float_or_none(expense.cfdi_tax_rate),
        sap_tax_index_override=expense.sap_tax_index_override,
        cfdi_currency=expense.cfdi_currency,
        facturas=_invoice_count(evidence_expense),
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
        es_hijo_particion=is_partition_child,
        id_original=expense.partition_parent_expense_id,
        particion_index=partition_index,
        total_particiones=partition_count,
        es_particionado=has_partition_children,
        inactivo=has_partition_children,
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
    try:
        validate_expense_date_for_reimbursement(
            spent_on,
            previous_ends_on=request.previous_reimbursement_ends_on,
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

    if request.reimbursement_starts_on is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REIMBURSEMENT_COVERAGE_MISSING",
                "message": (
                    "La solicitud no tiene un inicio de "
                    "periodo de reembolso calculado."
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
    if (
        category_requires_manual_authorization_area(category)
        and not (expense_in.authorization_area_name or "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "AUTHORIZATION_AREA_REQUIRED",
                "message": "Selecciona el área que autoriza para Pasajes y Taxis.",
            },
        )

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

    authorization_decision = resolve_expense_authorization(
        db,
        explicit=expense_in.requiere_autorizacion,
        category=category,
        amount=amount,
        description=expense_in.observaciones,
        merchant=merchant,
        authorization_area_id=authorization_area.id if authorization_area else None,
        store_code=store_code,
    )

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
        authorization_area_id=authorization_decision.authorization_area_id,
        requires_authorization=authorization_decision.requires_authorization,
    )


def _frontend_tax_rate_for_expense(
    *,
    category: str,
    store_code: str,
    requested_tax_rate: Decimal | None,
) -> Decimal:
    return determinar_tasa_iva_para_gasto(
        descripcion=category,
        numero_tienda=store_code,
        porcentaje_iva=requested_tax_rate,
    )


def _tax_amounts_from_rate(amount: Decimal, tax_rate: Decimal) -> tuple[Decimal, Decimal]:
    normalized_rate = _rate_or_none(tax_rate)
    rate = normalized_rate if normalized_rate is not None else Decimal("0.00")
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
    if (
        not user_can_transition_store_request(db, current_user, request.store_id)
        and (
            current_user.role != UserRole.authorizer
            or request.status
            not in {
                ReimbursementRequestStatus.submitted,
                ReimbursementRequestStatus.authorization_review,
            }
            or not _request_is_visible_for_role(request, current_user, db)
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the request store",
            },
        )
    if not _request_is_visible_for_role(request, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "REQUEST_NOT_VISIBLE_FOR_ROLE",
                "message": "This request is not available for the current role",
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
    today = datetime.now(MEXICO_CITY_TZ).date()
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

    if current_user.role == UserRole.accountant:
        return not has_pending_authorization

    return True


def _should_scope_queue_to_assigned_stores(current_user: User, db: Session) -> bool:
    if current_user.role in {
        UserRole.accountant,
        *GLOBAL_POST_ACCOUNTING_ROLES,
    }:
        return False
    return not (
        current_user.role == UserRole.authorizer
        and authorizer_has_global_authorization_area(db, current_user)
    )


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
        try:
            return date.fromisoformat(stripped)
        except ValueError:
            pass

        for separator in ("-", "/"):
            try:
                day, month, year = stripped.split(separator)
                if len(year) == 4:
                    return date(int(year), int(month), int(day))
            except ValueError:
                continue
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_FRONTEND_DATE",
                "message": "Expense date must use YYYY-MM-DD, DD-MM-YYYY or DD/MM/YYYY",
            },
        )

    today = datetime.now(MEXICO_CITY_TZ).date()
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


def _expense_evidence_source(expense: Expense) -> Expense:
    return expense.partition_parent if expense.partition_parent is not None else expense


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
