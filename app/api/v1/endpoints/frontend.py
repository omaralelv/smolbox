from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.attachment import AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense, ExpenseStatus
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.store import Store, StoreUserAssignment
from app.models.user import User, UserRole
from app.schemas.frontend import (
    FrontendContextRead,
    FrontendGastoCreate,
    FrontendGastoRead,
    FrontendSolicitudCreate,
    FrontendSolicitudRead,
    FrontendStoreRead,
    FrontendUserRead,
)
from app.services.accounting_queue import mark_accounting_request_taken_on_open
from app.services.expense_authorization_rules import expense_requires_authorization
from app.services.frontend_actions import available_actions_for_request
from app.services.permissions import user_can_transition_store_request, user_has_store_assignment
from app.services.reimbursement_validation import summarize_reimbursement_request

router = APIRouter()

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
        ReimbursementRequestStatus.paid,
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
    ReimbursementRequestStatus.paid,
    ReimbursementRequestStatus.rejected,
}

HISTORICAL_STATUSES = {
    ReimbursementRequestStatus.paid,
    ReimbursementRequestStatus.closed,
    ReimbursementRequestStatus.rejected,
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
        return [_request_payload(request, current_user) for request in requests]

    if current_user.role == UserRole.admin:
        statement = statement.where(
            ReimbursementRequest.status.not_in(
                {
                    ReimbursementRequestStatus.draft,
                    ReimbursementRequestStatus.rejected,
                }
            )
        )
        requests = list(db.scalars(statement.limit(200)))
        return [_request_payload(request, current_user) for request in requests]

    statuses = ROLE_QUEUE_STATUSES.get(current_user.role, set())
    if not statuses:
        return []

    statement = statement.where(ReimbursementRequest.status.in_(statuses))
    if current_user.role not in {UserRole.treasury, UserRole.director}:
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
        if _request_is_visible_for_role(request, current_user.role)
    ]
    return [_request_payload(request, current_user) for request in requests]


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
    if current_user.role not in {UserRole.treasury, UserRole.director, UserRole.admin}:
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
    return [_request_payload(request, current_user) for request in requests]


@router.get("/solicitudes/{request_identifier}/me", response_model=FrontendSolicitudRead)
def get_frontend_request_detail(
    request_identifier: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FrontendSolicitudRead:
    request = _get_request_by_frontend_identifier(request_identifier, db)
    _ensure_request_visible(request, current_user, db)
    request = _mark_accounting_request_taken_if_needed(request, current_user, db)
    return _request_payload(request, current_user)


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

    store = _resolve_store_for_create(request_in, current_user, db)
    period = _resolve_period_for_create(request_in, db)
    reported_total = request_in.reported_total
    if reported_total is None:
        reported_total = sum((expense.monto for expense in request_in.gastos), Decimal("0.00"))

    request = ReimbursementRequest(
        store_id=store.id,
        period_id=period.id,
        reported_total=_money(reported_total),
        notes=request_in.notes,
        folio=_generate_request_folio(store, db),
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
        db.add(_expense_from_frontend(expense_in, request=request, period=period))

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
    return _request_payload(request, current_user)


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

    expense = _expense_from_frontend(expense_in, request=request, period=request.period)
    db.add(expense)
    db.flush()
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
    return _request_payload(request, current_user)


def _request_detail_statement():
    return select(ReimbursementRequest).options(
        selectinload(ReimbursementRequest.store),
        selectinload(ReimbursementRequest.period),
        selectinload(ReimbursementRequest.attachments),
        selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
        selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
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
) -> FrontendSolicitudRead:
    summary = summarize_reimbursement_request(request)
    actions = available_actions_for_request(request, actor=current_user, summary=summary)
    display_date = _request_display_date(request)
    folio = request.folio or f"Solicitud {str(request.id)[:8]}"
    calculated_total = _money(summary.calculated_total)
    reported_total = _money(request.reported_total) if request.reported_total is not None else None
    return FrontendSolicitudRead(
        id=folio,
        backend_id=request.id,
        folio=folio,
        tienda=_frontend_store_code(request.store),
        fecha=_format_date(display_date),
        fecha_formateada=display_date.strftime("%d%m%Y"),
        status=_frontend_request_status(request.status),
        backend_status=request.status.value,
        accounting_queue_status=(
            request.accounting_queue_status.value if request.accounting_queue_status else None
        ),
        gerente=request.store.manager_name,
        cuenta_bancaria=request.store.bank_account,
        estado_region=request.store.state_region,
        gastos=[
            _expense_payload(expense)
            for expense in sorted(_frontend_visible_expenses(request.expenses), key=_expense_sort_key)
        ],
        monto_total=float(calculated_total),
        reported_total=float(reported_total) if reported_total is not None else None,
        calculated_total=float(calculated_total),
        expense_count=summary.expense_count,
        available_actions=actions,
        action_labels={action: ACTION_LABELS.get(action, action) for action in actions},
    )


def _frontend_visible_expenses(expenses: list[Expense]) -> list[Expense]:
    return list(expenses)


def _expense_payload(expense: Expense) -> FrontendGastoRead:
    category = expense.category or "Gasto General"
    folio = expense.cfdi_uuid or "N/A"
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
        download_url=_first_receipt_download_url(expense),
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
) -> Expense:
    spent_on = _parse_frontend_date(expense_in.fecha, period)
    if not period.starts_on <= spent_on <= period.ends_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "EXPENSE_OUTSIDE_PERIOD",
                "message": "The expense date is outside the reimbursement period",
                "spent_on": spent_on.isoformat(),
                "period_starts_on": period.starts_on.isoformat(),
                "period_ends_on": period.ends_on.isoformat(),
            },
        )
    category = expense_in.categoria or "Gasto General"
    merchant = expense_in.merchant or expense_in.proveedor or f"Gasto - {category}"
    return Expense(
        reimbursement_request_id=request.id,
        period_id=period.id,
        merchant=merchant,
        amount=_money(expense_in.monto),
        currency=expense_in.moneda.upper(),
        spent_on=spent_on,
        category=category,
        description=expense_in.observaciones,
        cfdi_uuid=expense_in.cfdi_uuid or expense_in.folio,
        cfdi_subtotal=_money_or_none(expense_in.cfdi_subtotal),
        cfdi_total=_money_or_none(expense_in.cfdi_total),
        cfdi_currency=(expense_in.cfdi_currency or expense_in.moneda).upper(),
        cfdi_tax_amount=_money_or_none(expense_in.cfdi_tax_amount),
        cfdi_tax_rate=_rate_or_none(expense_in.cfdi_tax_rate),
        requires_authorization=expense_requires_authorization(
            explicit=expense_in.requiere_autorizacion,
            category=category,
            description=expense_in.observaciones,
            merchant=merchant,
        ),
    )


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


def _generate_request_folio(store: Store, db: Session) -> str:
    prefix = f"{_frontend_store_code(store)}-{datetime.now(UTC).date():%d%m%Y}"
    existing_folios = db.scalars(
        select(ReimbursementRequest.folio).where(
            ReimbursementRequest.folio.is_not(None),
            ReimbursementRequest.folio.like(f"{prefix}%"),
        )
    )
    highest_sequence = 0
    for folio in existing_folios:
        if folio is None or not folio.startswith(prefix):
            continue
        suffix = folio.removeprefix(prefix)
        if suffix.isdecimal():
            highest_sequence = max(highest_sequence, int(suffix))
    return f"{prefix}{highest_sequence + 1}"


def _frontend_store_code(store: Store) -> str:
    candidate = store.code.removeprefix("HUD-")
    if len(candidate) == 4 and candidate.startswith("T") and candidate[1:].isdecimal():
        return candidate
    return store.code


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
    return 1 if expense.cfdi_uuid else 0


def _first_receipt_download_url(expense: Expense) -> str | None:
    receipt = next(
        (
            attachment
            for attachment in sorted(expense.attachments, key=lambda item: item.uploaded_at)
            if attachment.attachment_type == AttachmentType.receipt
        ),
        None,
    )
    if receipt is None:
        return None
    return f"/api/v1/attachments/{receipt.id}/download/me"


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _money_or_none(value: Decimal | None) -> Decimal | None:
    return _money(value) if value is not None else None


def _rate_or_none(value: Decimal | None) -> Decimal | None:
    return Decimal(value).quantize(Decimal("0.01")) if value is not None else None


def _float_or_none(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
