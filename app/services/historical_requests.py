from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.audit_log import AuditActorType, AuditLog
from app.models.historical_request import HistoricalAttachment, HistoricalExpense, HistoricalRequest
from app.models.store import Store, StoreUserAssignment
from app.models.user import User, UserRole
from app.schemas.audit_log import AuditLogRead, FrontendAuditLogRead
from app.schemas.frontend import FrontendGastoRead, FrontendSolicitudRead, FrontendStoreRead

EDIT_ROLES = {UserRole.admin, UserRole.accountant}
GLOBAL_READ_ROLES = EDIT_ROLES | {UserRole.accounting_manager, UserRole.treasury, UserRole.director}
MEXICO = ZoneInfo("America/Mexico_City")


def next_historical_folio(db: Session, store: Store, registered_on: date) -> str:
    # Serialize registrations by store; normal reimbursement counters are not read or changed.
    locked_store = db.execute(
        select(Store)
        .where(Store.id == store.id)
        .execution_options(populate_existing=True)
        .with_for_update()
    ).scalar_one()
    prefix = f"E-{locked_store.code}-{registered_on:%d%m%Y}"
    folios = db.scalars(
        select(HistoricalRequest.folio).where(
            HistoricalRequest.folio.startswith(prefix, autoescape=True),
        )
    )
    highest = max(
        (
            int(folio.removeprefix(prefix))
            for folio in folios
            if folio and folio.removeprefix(prefix).isdecimal()
        ),
        default=0,
    )
    return f"{prefix}{highest + 1}"


def ensure_editor(actor: User) -> None:
    if actor.role not in EDIT_ROLES:
        raise HTTPException(403, "Solo Admin y Contabilidad pueden capturar extemporáneos.")


def eligible_stores(db: Session) -> list[Store]:
    return list(
        db.scalars(
            select(Store)
            .where(
                Store.id.in_(
                    select(StoreUserAssignment.store_id)
                    .join(User, User.id == StoreUserAssignment.user_id)
                    .where(
                        StoreUserAssignment.is_active.is_(True),
                        StoreUserAssignment.role == UserRole.store,
                        User.is_active.is_(True),
                        User.role == UserRole.store,
                    ),
                )
            )
            .order_by(Store.code)
        )
    )


def store_payload(store: Store) -> FrontendStoreRead:
    return FrontendStoreRead(
        id=store.id,
        code=store.code,
        name=store.name,
        gerente=store.manager_name,
        cuenta_bancaria=store.bank_account,
        estado_region=store.state_region,
    )


def request_statement():
    return select(HistoricalRequest).options(
        selectinload(HistoricalRequest.store),
        selectinload(HistoricalRequest.expenses).selectinload(HistoricalExpense.attachments),
    )


def visible_request_ids(actor: User, db: Session):
    statement = request_statement().where(HistoricalRequest.status == "paid")
    if actor.role not in GLOBAL_READ_ROLES:
        statement = statement.where(
            HistoricalRequest.store_id.in_(
                select(StoreUserAssignment.store_id).where(
                    StoreUserAssignment.user_id == actor.id,
                    StoreUserAssignment.is_active.is_(True),
                    StoreUserAssignment.role == actor.role,
                ),
            )
        )
    return statement


def get_request(
    db: Session, identifier: UUID, actor: User, *, edit: bool = False
) -> HistoricalRequest:
    request = db.scalar(
        request_statement()
        .where(HistoricalRequest.id == identifier)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if request is None:
        raise HTTPException(404, "Registro extemporáneo no encontrado.")
    if edit or request.status == "draft":
        ensure_editor(actor)
        if request.created_by_user_id != actor.id:
            raise HTTPException(403, "El borrador pertenece a otro usuario.")
        if edit and request.status != "draft":
            raise HTTPException(
                409, "El registro extemporáneo ya está en Histórico y es de solo lectura."
            )
    elif (
        db.scalar(visible_request_ids(actor, db).where(HistoricalRequest.id == request.id)) is None
    ):
        raise HTTPException(403, "No tienes permiso para consultar este registro extemporáneo.")
    return request


def get_expense(
    db: Session, identifier: UUID, actor: User, *, edit: bool = False
) -> HistoricalExpense:
    expense = db.get(HistoricalExpense, identifier)
    if expense is None:
        raise HTTPException(404, "Gasto extemporáneo no encontrado.")
    get_request(db, expense.request_id, actor, edit=edit)
    if edit and expense.removed_at is not None:
        raise HTTPException(409, "El gasto ya fue eliminado.")
    return expense


def audit_event(
    db: Session,
    request: HistoricalRequest,
    actor: User,
    action: str,
    message: str,
    *,
    expense: HistoricalExpense | None = None,
    event_id: UUID | None = None,
    payload: dict | None = None,
) -> AuditLog:
    existing = db.get(AuditLog, event_id) if event_id else None
    if existing is not None:
        data = existing.event_payload or {}
        if (
            existing.actor_user_id != actor.id
            or data.get("historical_request_id") != str(request.id)
            or existing.action != action
            or existing.message != message
            or data.get("expense_id") != (str(expense.id) if expense else None)
        ):
            raise HTTPException(409, "El identificador del movimiento ya fue utilizado.")
        return existing
    event = AuditLog(
        id=event_id or uuid4(),
        actor_user_id=actor.id,
        actor_type=AuditActorType.user,
        action=action,
        message=message,
        created_at=datetime.now(UTC),
        event_payload={
            **(payload or {}),
            "historical_request_id": str(request.id),
            "expense_id": str(expense.id) if expense else None,
            "store_id": str(request.store_id),
            "store_code": request.store.code,
            "request_folio": request.folio or f"Borrador extemporáneo {request.id}",
            "actor_name": actor.full_name,
            "actor_role": actor.role.value,
            "es_extemporaneo": True,
        },
    )
    db.add(event)
    return event


def event_payload(event: AuditLog) -> FrontendAuditLogRead:
    payload = event.event_payload or {}
    data = AuditLogRead.model_validate(event).model_dump()
    data["expense_id"] = payload.get("expense_id")
    return FrontendAuditLogRead(
        **data,
        store_code=payload.get("store_code"),
        request_folio=payload.get("request_folio"),
        actor_name=payload.get("actor_name"),
        actor_role=payload.get("actor_role"),
    )


def request_payload(request: HistoricalRequest, actor: User) -> FrontendSolicitudRead:
    expenses = sorted(
        (e for e in request.expenses if e.removed_at is None),
        key=lambda e: (
            e.created_at.replace(tzinfo=e.created_at.tzinfo or UTC),
            str(e.id),
        ),
    )
    total = sum((expense.amount for expense in expenses), Decimal("0.00"))
    timestamp = request.registered_at or request.created_at
    date = timestamp.replace(tzinfo=timestamp.tzinfo or UTC).astimezone(MEXICO)
    return FrontendSolicitudRead(
        id=request.folio or f"E-BORRADOR-{request.id}",
        backend_id=request.id,
        folio=request.folio or "Borrador extemporáneo",
        tienda=request.store.code,
        fecha=date.strftime("%d/%m/%Y"),
        fecha_formateada=date.strftime("%d%m%Y"),
        status="Pagada" if request.status == "paid" else "Borrador",
        backend_status="historical_paid" if request.status == "paid" else "historical_draft",
        es_extemporaneo=True,
        gerente=request.store.manager_name,
        cuenta_bancaria=request.store.bank_account,
        estado_region=request.store.state_region,
        gastos=[expense_payload(expense, actor) for expense in expenses],
        monto_total=float(total),
        reported_total=float(total),
        calculated_total=float(total),
        expense_count=len(expenses),
        available_actions=[],
    )


def expense_payload(expense: HistoricalExpense, actor: User) -> FrontendGastoRead:
    attachments = sorted(
        expense.attachments,
        key=lambda a: (
            a.uploaded_at.replace(tzinfo=a.uploaded_at.tzinfo or UTC),
            str(a.id),
        ),
    )
    url = attachment_url(attachments[-1]) if attachments else None
    fiscal = expense.fiscal_data or {}
    return FrontendGastoRead(
        id=str(expense.id),
        backend_id=expense.id,
        capture_id=expense.client_id,
        nombre=f"Gasto - {expense.category}",
        fecha=expense.spent_on,
        monto=float(expense.amount),
        tipo=expense.category,
        type=expense.category,
        folio=expense.cfdi_uuid or "N/A",
        folio_fiscal=expense.cfdi_uuid,
        observaciones=expense.notes or "",
        created_at=expense.created_at.replace(tzinfo=UTC),
        can_add_observation=expense.request.status == "draft"
        and expense.request.created_by_user_id == actor.id,
        cfdi_subtotal=fiscal.get("cfdi_subtotal"),
        cfdi_total=fiscal.get("cfdi_total"),
        cfdi_tax_amount=fiscal.get("cfdi_tax_amount"),
        cfdi_tax_rate=fiscal.get("cfdi_tax_rate"),
        cfdi_currency=fiscal.get("cfdi_currency"),
        facturas=1 if attachments else 0,
        autorizacion="No aplica",
        status="Registrado",
        backend_status="historical",
        requires_authorization=False,
        download_url=url,
        url_factura=url if expense.document_type == "factura" else None,
        url_vale=url if expense.document_type == "vale" else None,
        url_recibo=url if expense.document_type == "recibo" else None,
    )


def attachment_url(attachment: HistoricalAttachment) -> str:
    return f"/api/v1/frontend/extemporaneos/attachments/{attachment.id}/download/me"
