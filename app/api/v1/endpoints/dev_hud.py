from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.cfdi_validation import CfdiValidation
from app.models.expense import Expense
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.store import Store
from app.models.user import User, UserRole
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.storage import StorageService
from app.services.workflow import WorkflowTransitionError, transition_reimbursement_request

router = APIRouter()

HUD_STORE_CODE = "HUD-001"
HUD_PERIOD_NAME = "HUD Agosto 2026"
HUD_EMAIL_DOMAIN = "hud.smolbox.local"

DEMO_RECEIPT_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"

DEMO_USERS = {
    UserRole.store: ("hud.store@hud.smolbox.local", "HUD Usuario Tienda"),
    UserRole.accountant: ("hud.accountant@hud.smolbox.local", "HUD Usuario Contador"),
    UserRole.treasury: ("hud.treasury@hud.smolbox.local", "HUD Usuario Tesoreria"),
    UserRole.admin: ("hud.admin@hud.smolbox.local", "HUD Usuario Admin"),
}


@router.get("/status")
def get_dev_hud_status(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    try:
        db.execute(select(1))
        counts = {
            "stores": _count(db, Store),
            "periods": _count(db, Period),
            "users": _count(db, User),
            "reimbursement_requests": _count(db, ReimbursementRequest),
            "expenses": _count(db, Expense),
            "attachments": _count(db, Attachment),
            "audit_events": _count(db, AuditLog),
            "cfdi_validations": _count(db, CfdiValidation),
        }
        database_status = "ok"
        api_status = "ok"
    except SQLAlchemyError:
        return {
            "api_status": "degraded",
            "database": "unavailable",
            "environment": settings.environment,
            "counts": {},
            "scenario": {"exists": False},
        }

    return {
        "api_status": api_status,
        "database": database_status,
        "environment": settings.environment,
        "counts": counts,
        "scenario": _scenario_payload(db),
    }


@router.post("/seed-demo", status_code=status.HTTP_201_CREATED)
def seed_dev_hud_demo(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    request = _ensure_demo_dataset(db, storage)
    request_id = request.id
    db.commit()

    return {
        "message": "HUD demo scenario is ready",
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/complete-cfdi")
def complete_dev_hud_cfdi(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    added = 0
    for expense in request.expenses:
        if _has_current_valid_cfdi(expense):
            continue
        _ensure_demo_cfdi(db, storage, expense, settings)
        added += 1

    if added:
        db.add(
            AuditLog(
                reimbursement_request_id=request.id,
                actor_type=AuditActorType.system,
                action="dev_hud_cfdi_completed",
                message=f"Created {added} synthetic CFDI validations for HUD testing.",
                event_payload={"added": added},
            )
        )
    request_id = request.id
    db.commit()

    return {
        "message": "HUD CFDI evidence completed",
        "cfdi_added": added,
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/transition/{target_status}")
def transition_dev_hud_request(
    target_status: ReimbursementRequestStatus,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    request = _load_demo_request(db)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "HUD_SCENARIO_NOT_FOUND", "message": "Create the HUD scenario first"},
        )

    actor = _actor_for_transition(db, request.status, target_status)
    summary = summarize_reimbursement_request(request)
    try:
        from_status, to_status = transition_reimbursement_request(
            request,
            actor=actor,
            target_status=target_status,
            summary=summary,
        )
    except WorkflowTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_WORKFLOW_TRANSITION", "message": str(exc)},
        ) from exc

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="dev_hud_request_status_changed",
            from_status=from_status.value,
            to_status=to_status.value,
            message=f"HUD moved request to {to_status.value}.",
            event_payload={"actor_role": actor.role.value},
        )
    )
    request_id = request.id
    actor_payload = {"id": actor.id, "email": actor.email, "role": actor.role.value}
    db.commit()

    return {
        "message": "HUD request transitioned",
        "from_status": from_status.value,
        "to_status": to_status.value,
        "actor": actor_payload,
        "scenario": _scenario_payload(db, request_id),
    }


@router.post("/reset-demo")
def reset_dev_hud_demo(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    _ensure_dev_hud_enabled(settings)

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    deleted = _delete_demo_dataset(db, storage)
    db.commit()

    return {
        "message": "HUD demo data deleted",
        "deleted": deleted,
        "scenario": {"exists": False},
    }


def _ensure_dev_hud_enabled(settings: Settings) -> None:
    if settings.environment.lower() == "production":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def _ensure_demo_dataset(db: Session, storage: StorageService) -> ReimbursementRequest:
    users = {role: _get_or_create_user(db, role) for role in DEMO_USERS}
    store = _get_or_create_store(db)
    period = _get_or_create_period(db)
    request = _get_or_create_request(db, store, period)
    if not request.expenses:
        request.expenses.extend(_create_demo_expenses(db, request))
        db.flush()

    for expense in request.expenses:
        _ensure_demo_receipt(db, storage, expense)

    db.add(
        AuditLog(
            reimbursement_request_id=request.id,
            actor_user_id=users[UserRole.admin].id,
            actor_type=AuditActorType.user,
            action="dev_hud_seeded",
            message="HUD demo scenario seeded.",
            event_payload={"store_code": store.code, "period_name": period.name},
        )
    )
    return request


def _get_or_create_user(db: Session, role: UserRole) -> User:
    email, full_name = DEMO_USERS[role]
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        user.full_name = full_name
        user.role = role
        user.is_active = True
        return user

    user = User(email=email, full_name=full_name, role=role, is_active=True)
    db.add(user)
    db.flush()
    return user


def _get_or_create_store(db: Session) -> Store:
    store = db.scalar(select(Store).where(Store.code == HUD_STORE_CODE))
    if store is not None:
        store.name = "HUD Tienda Centro"
        store.contact_email = "hud.store@hud.smolbox.local"
        store.assigned_accountant = "HUD Usuario Contador"
        return store

    store = Store(
        code=HUD_STORE_CODE,
        name="HUD Tienda Centro",
        contact_email="hud.store@hud.smolbox.local",
        assigned_accountant="HUD Usuario Contador",
    )
    db.add(store)
    db.flush()
    return store


def _get_or_create_period(db: Session) -> Period:
    period = db.scalar(select(Period).where(Period.name == HUD_PERIOD_NAME))
    if period is not None:
        period.starts_on = date(2026, 8, 1)
        period.ends_on = date(2026, 8, 31)
        period.status = PeriodStatus.open
        return period

    period = Period(
        name=HUD_PERIOD_NAME,
        starts_on=date(2026, 8, 1),
        ends_on=date(2026, 8, 31),
        status=PeriodStatus.open,
    )
    db.add(period)
    db.flush()
    return period


def _get_or_create_request(
    db: Session,
    store: Store,
    period: Period,
) -> ReimbursementRequest:
    request = db.scalar(
        select(ReimbursementRequest)
        .options(selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments))
        .where(
            ReimbursementRequest.store_id == store.id,
            ReimbursementRequest.period_id == period.id,
        )
    )
    if request is not None:
        request.reported_total = Decimal("1500.00")
        request.notes = "Escenario local para probar el backend de Smolbox."
        return request

    request = ReimbursementRequest(
        store_id=store.id,
        period_id=period.id,
        reported_total=Decimal("1500.00"),
        previous_reimbursement_starts_on=date(2026, 7, 1),
        previous_reimbursement_ends_on=date(2026, 7, 31),
        previous_reimbursement_amount=Decimal("1400.00"),
        notes="Escenario local para probar el backend de Smolbox.",
    )
    db.add(request)
    db.flush()
    return request


def _create_demo_expenses(db: Session, request: ReimbursementRequest) -> list[Expense]:
    expenses = [
        Expense(
            period_id=request.period_id,
            reimbursement_request_id=request.id,
            merchant="HUD Papeleria Uno",
            amount=Decimal("1000.00"),
            currency="MXN",
            spent_on=date(2026, 8, 10),
            category="papeleria",
            description="Hojas, toner y material de oficina.",
            supplier_tax_id="XAXX010101000",
        ),
        Expense(
            period_id=request.period_id,
            reimbursement_request_id=request.id,
            merchant="HUD Taxi Demo",
            amount=Decimal("500.00"),
            currency="MXN",
            spent_on=date(2026, 8, 11),
            category="transporte",
            description="Traslado local operativo.",
            supplier_tax_id="XEXX010101000",
        ),
    ]
    for expense in expenses:
        db.add(expense)
    return expenses


def _ensure_demo_receipt(db: Session, storage: StorageService, expense: Expense) -> None:
    if _has_attachment_type(expense, AttachmentType.receipt):
        return

    stored = storage.save_bytes(
        DEMO_RECEIPT_BYTES,
        filename=f"{expense.merchant.lower().replace(' ', '-')}-ticket.pdf",
        expense_id=expense.id,
    )
    attachment = Attachment(
        expense_id=expense.id,
        attachment_type=AttachmentType.receipt,
        filename=stored.filename,
        content_type="application/pdf",
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    expense.attachments.append(attachment)
    db.add(attachment)


def _ensure_demo_cfdi(
    db: Session,
    storage: StorageService,
    expense: Expense,
    settings: Settings,
) -> None:
    cfdi_uuid = str(uuid5(NAMESPACE_URL, f"smolbox-hud-cfdi:{expense.id}")).upper()
    issuer_rfc = expense.supplier_tax_id or "XAXX010101000"
    receiver_rfc = settings.cfdi_receiver_rfc or "BBB010101BBB"
    issued_at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    content = _demo_cfdi_xml(
        uuid=cfdi_uuid,
        issuer_rfc=issuer_rfc,
        receiver_rfc=receiver_rfc,
        amount=expense.amount,
        currency=expense.currency,
        issued_at=issued_at,
    )
    stored = storage.save_bytes(
        content,
        filename=f"{expense.merchant.lower().replace(' ', '-')}-cfdi.xml",
        expense_id=expense.id,
    )
    attachment = Attachment(
        expense_id=expense.id,
        attachment_type=AttachmentType.cfdi_xml,
        filename=stored.filename,
        content_type="application/xml",
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    expense.attachments.append(attachment)
    db.add(attachment)
    db.flush()

    db.execute(
        update(CfdiValidation)
        .where(CfdiValidation.expense_id == expense.id, CfdiValidation.is_current.is_(True))
        .values(is_current=False)
    )
    validation = CfdiValidation(
        expense_id=expense.id,
        attachment_id=attachment.id,
        uuid=cfdi_uuid,
        issuer_rfc=issuer_rfc,
        receiver_rfc=receiver_rfc,
        total=expense.amount,
        currency=expense.currency,
        issued_at=issued_at,
        is_valid=True,
        issues=[],
        checksum_sha256=stored.checksum_sha256,
        validator_version="dev-hud",
        is_current=True,
    )
    expense.cfdi_validations.append(validation)
    db.add(validation)
    expense.cfdi_uuid = cfdi_uuid
    expense.cfdi_issuer_rfc = issuer_rfc
    expense.cfdi_receiver_rfc = receiver_rfc
    expense.cfdi_total = expense.amount
    expense.cfdi_currency = expense.currency


def _demo_cfdi_xml(
    *,
    uuid: str,
    issuer_rfc: str,
    receiver_rfc: str,
    amount: Decimal,
    currency: str,
    issued_at: datetime,
) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
  xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
  xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
  Version="4.0"
  Fecha="{issued_at.strftime("%Y-%m-%dT%H:%M:%S")}"
  Total="{amount}"
  Moneda="{currency}">
  <cfdi:Emisor Rfc="{issuer_rfc}" Nombre="HUD PROVEEDOR"/>
  <cfdi:Receptor Rfc="{receiver_rfc}" Nombre="SMOLBOX HUD"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
""".encode()


def _load_demo_request(db: Session, request_id: UUID | None = None) -> ReimbursementRequest | None:
    statement = (
        select(ReimbursementRequest)
        .join(Store)
        .join(Period)
        .options(
            selectinload(ReimbursementRequest.store),
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
            selectinload(ReimbursementRequest.audit_events),
        )
        .where(Store.code == HUD_STORE_CODE, Period.name == HUD_PERIOD_NAME)
    )
    if request_id is not None:
        statement = statement.where(ReimbursementRequest.id == request_id)
    return db.scalars(statement).first()


def _scenario_payload(db: Session, request_id: UUID | None = None) -> dict[str, Any]:
    request = _load_demo_request(db, request_id)
    if request is None:
        return {"exists": False}

    summary = summarize_reimbursement_request(request)
    users = {
        role.value: _user_payload(db.scalar(select(User).where(User.email == email)))
        for role, (email, _) in DEMO_USERS.items()
    }
    audit_events = sorted(request.audit_events, key=lambda event: event.created_at, reverse=True)

    return {
        "exists": True,
        "request_id": request.id,
        "status": request.status.value,
        "store_id": request.store_id,
        "store_code": request.store.code,
        "store_name": request.store.name,
        "period_id": request.period_id,
        "period_name": request.period.name,
        "users": users,
        "summary": summary.model_dump(mode="json"),
        "expenses": [_expense_payload(expense) for expense in request.expenses],
        "audit_events": [
            {
                "id": event.id,
                "action": event.action,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "message": event.message,
                "created_at": event.created_at,
            }
            for event in audit_events[:10]
        ],
    }


def _user_payload(user: User | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }


def _expense_payload(expense: Expense) -> dict[str, Any]:
    return {
        "id": expense.id,
        "merchant": expense.merchant,
        "amount": expense.amount,
        "currency": expense.currency,
        "spent_on": expense.spent_on,
        "category": expense.category,
        "has_receipt": _has_attachment_type(expense, AttachmentType.receipt),
        "has_cfdi_xml": _has_attachment_type(expense, AttachmentType.cfdi_xml),
        "has_current_valid_cfdi": _has_current_valid_cfdi(expense),
    }


def _has_attachment_type(expense: Expense, attachment_type: AttachmentType) -> bool:
    return any(attachment.attachment_type == attachment_type for attachment in expense.attachments)


def _has_current_valid_cfdi(expense: Expense) -> bool:
    return any(
        validation.is_current and validation.is_valid
        for validation in expense.cfdi_validations
    )


def _actor_for_transition(
    db: Session,
    current_status: ReimbursementRequestStatus,
    target_status: ReimbursementRequestStatus,
) -> User:
    if target_status == ReimbursementRequestStatus.submitted:
        role = UserRole.store
    elif target_status in {
        ReimbursementRequestStatus.under_accounting_review,
        ReimbursementRequestStatus.correction_required,
        ReimbursementRequestStatus.accounting_approved,
    }:
        role = UserRole.accountant
    elif target_status == ReimbursementRequestStatus.rejected:
        role = (
            UserRole.treasury
            if current_status == ReimbursementRequestStatus.treasury_review
            else UserRole.accountant
        )
    else:
        role = UserRole.treasury

    actor = db.scalar(select(User).where(User.email == DEMO_USERS[role][0]))
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "HUD_ACTOR_NOT_FOUND", "message": "Seed the HUD scenario first"},
        )
    return actor


def _delete_demo_dataset(db: Session, storage: StorageService) -> dict[str, int]:
    hud_user_ids = list(
        db.scalars(select(User.id).where(User.email.like(f"%@{HUD_EMAIL_DOMAIN}")))
    )
    hud_store_ids = list(db.scalars(select(Store.id).where(Store.code.like("HUD-%"))))
    hud_period_ids = list(db.scalars(select(Period.id).where(Period.name.like("HUD %"))))

    request_filters = []
    if hud_store_ids:
        request_filters.append(ReimbursementRequest.store_id.in_(hud_store_ids))
    if hud_period_ids:
        request_filters.append(ReimbursementRequest.period_id.in_(hud_period_ids))
    request_ids = list(
        db.scalars(
            select(ReimbursementRequest.id).where(or_(*request_filters))
            if request_filters
            else select(ReimbursementRequest.id).where(False)
        )
    )

    expense_filters = []
    if request_ids:
        expense_filters.append(Expense.reimbursement_request_id.in_(request_ids))
    if hud_period_ids:
        expense_filters.append(Expense.period_id.in_(hud_period_ids))
    expense_ids = list(
        db.scalars(
            select(Expense.id).where(or_(*expense_filters))
            if expense_filters
            else select(Expense.id).where(False)
        )
    )

    attachment_filters = []
    if request_ids:
        attachment_filters.append(Attachment.reimbursement_request_id.in_(request_ids))
    if expense_ids:
        attachment_filters.append(Attachment.expense_id.in_(expense_ids))
    attachments = list(
        db.scalars(
            select(Attachment).where(or_(*attachment_filters))
            if attachment_filters
            else select(Attachment).where(False)
        )
    )

    deleted = {
        "cfdi_validations": _delete_where(db, CfdiValidation, CfdiValidation.expense_id, expense_ids),
        "attachments": len(attachments),
        "audit_events": _delete_audit_events(db, request_ids, expense_ids, hud_user_ids),
    }

    if attachments:
        db.execute(delete(Attachment).where(Attachment.id.in_([item.id for item in attachments])))
        for attachment in attachments:
            try:
                storage.delete(attachment.storage_path)
            except (OSError, ValueError):
                continue

    deleted.update(
        {
            "expenses": _delete_where(db, Expense, Expense.id, expense_ids),
            "reimbursement_requests": _delete_where(
                db,
                ReimbursementRequest,
                ReimbursementRequest.id,
                request_ids,
            ),
            "stores": _delete_where(db, Store, Store.id, hud_store_ids),
            "periods": _delete_where(db, Period, Period.id, hud_period_ids),
            "users": _delete_where(db, User, User.id, hud_user_ids),
        }
    )

    return deleted


def _delete_where(db: Session, model: type, column: Any, ids: list[UUID]) -> int:
    if not ids:
        return 0
    result = db.execute(delete(model).where(column.in_(ids)))
    return result.rowcount or 0


def _delete_audit_events(
    db: Session,
    request_ids: list[UUID],
    expense_ids: list[UUID],
    user_ids: list[UUID],
) -> int:
    filters = []
    if request_ids:
        filters.append(AuditLog.reimbursement_request_id.in_(request_ids))
    if expense_ids:
        filters.append(AuditLog.expense_id.in_(expense_ids))
    if user_ids:
        filters.append(AuditLog.actor_user_id.in_(user_ids))
    if not filters:
        return 0
    result = db.execute(delete(AuditLog).where(or_(*filters)))
    return result.rowcount or 0
