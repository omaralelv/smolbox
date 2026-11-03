from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated
from urllib.parse import quote
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.dependencies.auth import get_current_user
from app.api.v1.endpoints.attachments import _ocr_result_from_preview_token
from app.api.v1.endpoints.cfdi import _find_duplicate_cfdi_uuid, _preview_invoice_ocr
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import AttachmentType
from app.models.audit_log import AuditLog
from app.models.historical_request import HistoricalAttachment, HistoricalExpense, HistoricalRequest
from app.models.user import User, UserRole
from app.schemas.frontend import FrontendSolicitudRead, FrontendStoreRead
from app.schemas.historical_request import (
    HistoricalEventCreate,
    HistoricalExpenseCreate,
    HistoricalObservationCreate,
    HistoricalRegistration,
)
from app.services.cfdi_parser import CfdiParseError, parse_cfdi_xml
from app.services.cfdi_validator import normalize_cfdi_uuid, validate_cfdi_for_expense
from app.services.file_validation import InvalidAttachment, prepare_attachment_for_processing
from app.services.historical_requests import (
    MEXICO,
    audit_event,
    eligible_stores,
    ensure_editor,
    event_payload,
    get_expense,
    get_request,
    request_payload,
    request_statement,
    store_payload,
)
from app.services.ocr_receiver import assess_invoice_receiver
from app.services.storage import EmptyUpload, StorageService, UploadTooLarge, read_upload_limited
from app.services.tax_rules import determinar_tasa_iva_para_gasto
from app.services.textract_ocr import expected_invoice_receiver_message

router = APIRouter()
Actor = Annotated[User, Depends(get_current_user)]
Database = Annotated[Session, Depends(get_db)]
Configuration = Annotated[Settings, Depends(get_settings)]


@router.get("/stores/me", response_model=list[FrontendStoreRead])
def list_stores(actor: Actor, db: Database):
    ensure_editor(actor)
    return [store_payload(store) for store in eligible_stores(db)]


@router.get("/uuid/{uuid}/availability/me")
def uuid_availability(uuid: str, client_id: UUID, actor: Actor, db: Database):
    ensure_editor(actor)
    normalized = normalize_cfdi_uuid(uuid)
    if normalized is None:
        raise HTTPException(422, "Folio Fiscal inválido.")
    duplicates = _find_duplicate_cfdi_uuid(db, normalized)
    own_expense = db.scalar(
        select(HistoricalExpense).where(HistoricalExpense.client_id == client_id)
    )
    allowed = bool(
        own_expense
        and own_expense.request.created_by_user_id == actor.id
        and own_expense.request.status == "draft"
        and duplicates[0] == own_expense.id
        and duplicates[1] is None
    )
    return {"uuid": normalized, "is_available": not any(duplicates) or allowed}


@router.post("/stores/{store_id}/draft/me", response_model=FrontendSolicitudRead)
def ensure_draft(store_id: UUID, actor: Actor, db: Database):
    ensure_editor(actor)
    store = next((store for store in eligible_stores(db) if store.id == store_id), None)
    if store is None:
        raise HTTPException(404, "La tienda no tiene una asignación activa de Tienda.")
    statement = request_statement().where(
        HistoricalRequest.store_id == store_id,
        HistoricalRequest.created_by_user_id == actor.id,
        HistoricalRequest.status == "draft",
    )
    draft = db.scalar(statement)
    if draft is None:
        draft = HistoricalRequest(store_id=store_id, store=store, created_by_user_id=actor.id)
        try:
            db.add(draft)
            db.flush()
            audit_event(
                db, draft, actor, "historical_request_created", "Captura extemporánea iniciada."
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            draft = db.scalar(statement)
            if draft is None:
                raise
    return request_payload(draft, actor)


@router.get("/{request_id}/me", response_model=FrontendSolicitudRead)
def read_request(request_id: UUID, actor: Actor, db: Database):
    return request_payload(get_request(db, request_id, actor), actor)


@router.post("/{request_id}/expenses/me", response_model=FrontendSolicitudRead, status_code=201)
def add_expense(request_id: UUID, data: HistoricalExpenseCreate, actor: Actor, db: Database):
    request = get_request(db, request_id, actor, edit=True)
    existing = db.scalar(
        select(HistoricalExpense).where(HistoricalExpense.client_id == data.client_id)
    )
    fingerprint = data.model_dump(mode="json")
    if existing is not None:
        if existing.request_id != request.id or existing.fiscal_data.get("input") != fingerprint:
            raise HTTPException(409, "La captura ya se guardó con otros datos.")
        return request_payload(request, actor)
    try:
        spent_on = (
            data.fecha if isinstance(data.fecha, date) else date.fromisoformat(str(data.fecha))
        )
    except ValueError as exc:
        raise HTTPException(422, "La fecha debe tener formato AAAA-MM-DD.") from exc
    category = (data.categoria or "").strip()
    if not category or len(category) > 120:
        raise HTTPException(422, "Selecciona una categoría válida.")
    if (data.cfdi_currency or data.moneda or "MXN").upper() != "MXN":
        raise HTTPException(422, "La moneda del gasto debe ser MXN.")
    uuid = normalize_cfdi_uuid(data.cfdi_uuid or data.folio)
    if data.document_type == "factura" and uuid is None:
        raise HTTPException(422, "Captura manualmente el Folio Fiscal y presiona Confirmar.")
    if uuid and any(_find_duplicate_cfdi_uuid(db, uuid)):
        raise HTTPException(409, "El Folio Fiscal ya está registrado en otro gasto.")
    expense = HistoricalExpense(
        request=request,
        client_id=data.client_id,
        spent_on=spent_on,
        category=category,
        amount=data.monto,
        document_type=data.document_type,
        cfdi_uuid=uuid,
        notes=(data.observaciones or "").strip() or None,
        fiscal_data={
            **data.model_dump(
                mode="json",
                include={
                    "cfdi_subtotal",
                    "cfdi_total",
                    "cfdi_tax_amount",
                    "cfdi_tax_rate",
                    "cfdi_currency",
                },
            ),
            "input": fingerprint,
        },
    )
    if not expense.fiscal_data.get("cfdi_currency"):
        expense.fiscal_data["cfdi_currency"] = "MXN"
    rate = determinar_tasa_iva_para_gasto(
        descripcion=category,
        numero_tienda=request.store.code,
        porcentaje_iva=data.cfdi_tax_rate,
    )
    subtotal = (expense.amount / (1 + rate / 100)).quantize(Decimal("0.01"))
    expense.fiscal_data = {
        **expense.fiscal_data,
        "cfdi_tax_rate": str(rate),
        "cfdi_subtotal": str(subtotal),
        "cfdi_tax_amount": str(expense.amount - subtotal),
        "cfdi_total": str(expense.amount),
    }
    try:
        db.add(expense)
        db.flush()
        audit_event(
            db,
            request,
            actor,
            "historical_expense_created",
            f"Gasto extemporáneo - {category}. Monto: ${data.monto:.2f}.",
            expense=expense,
        )
        if expense.notes:
            audit_event(
                db,
                request,
                actor,
                "expense_observation_added",
                expense.notes,
                expense=expense,
                payload={"is_initial_observation": True},
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(HistoricalExpense).where(HistoricalExpense.client_id == data.client_id)
        )
        if (
            existing
            and existing.request_id == request_id
            and existing.fiscal_data.get("input") == fingerprint
        ):
            return request_payload(get_request(db, request_id, actor), actor)
        raise HTTPException(409, "El gasto o Folio Fiscal ya fue registrado.") from exc
    return request_payload(request, actor)


@router.delete("/expenses/{expense_id}/me", response_model=FrontendSolicitudRead)
def remove_expense(expense_id: UUID, actor: Actor, db: Database):
    expense = get_expense(db, expense_id, actor)
    request = get_request(db, expense.request_id, actor, edit=True)
    if expense.removed_at is None:
        expense.removed_at = datetime.now(UTC)
        audit_event(
            db,
            request,
            actor,
            "historical_expense_removed",
            f"Gasto extemporáneo eliminado: {expense.category}, ${expense.amount:.2f}.",
            expense=expense,
        )
        db.commit()
    return request_payload(request, actor)


@router.post("/{request_id}/register/me", response_model=FrontendSolicitudRead)
def register(
    request_id: UUID,
    data: HistoricalRegistration,
    actor: Actor,
    db: Database,
    settings: Configuration,
):
    request = get_request(db, request_id, actor)
    ensure_editor(actor)
    if request.created_by_user_id != actor.id:
        raise HTTPException(403, "El registro pertenece a otro usuario.")
    expenses = [expense for expense in request.expenses if expense.removed_at is None]
    if set(data.expected_expense_ids) != {expense.id for expense in expenses}:
        raise HTTPException(409, "Los gastos cambiaron. Actualiza antes de registrar.")
    if request.status == "paid":
        return request_payload(request, actor)
    if not expenses or any(not expense.attachments for expense in expenses):
        raise HTTPException(409, "Todos los gastos deben tener un comprobante válido.")
    if any(not attachment.ocr_data for expense in expenses for attachment in expense.attachments):
        raise HTTPException(409, "Falta validar un comprobante.")
    for expense in expenses:
        for attachment in expense.attachments:
            document_path(attachment, settings)
    for expense in expenses:
        if expense.cfdi_uuid:
            duplicate, validation = _find_duplicate_cfdi_uuid(db, expense.cfdi_uuid)
            if duplicate != expense.id or validation is not None:
                raise HTTPException(409, "El Folio Fiscal ya está registrado en otro gasto.")
    request.registered_at = datetime.now(UTC)
    request.status = "paid"
    request.folio = f"E-{request.store.code}-{request.registered_at.astimezone(MEXICO):%d%m%Y}-{request.id.hex.upper()}"
    audit_event(
        db,
        request,
        actor,
        "historical_request_registered",
        "Solicitud extemporánea registrada en Histórico como Pagada. Sin operación de pago.",
        payload={
            "total": str(sum((expense.amount for expense in expenses), Decimal(0))),
            "expense_count": len(expenses),
        },
    )
    db.commit()
    return request_payload(request, actor)


@router.post("/expenses/{expense_id}/attachments/me", status_code=201)
async def upload_document(
    expense_id: UUID,
    actor: Actor,
    db: Database,
    settings: Configuration,
    file: Annotated[UploadFile, File()],
    ocr_preview_token: Annotated[str | None, Form()] = None,
):
    expense = get_expense(db, expense_id, actor, edit=True)
    try:
        content = await read_upload_limited(file, settings.max_upload_bytes)
        attachment_type = (
            AttachmentType.cfdi_xml
            if (file.filename or "").lower().endswith(".xml")
            else AttachmentType.receipt
        )
        content_type, _prepared = await run_in_threadpool(
            prepare_attachment_for_processing,
            file.filename or "upload",
            content,
            attachment_type,
            max_bytes=settings.max_upload_bytes,
        )
    except (EmptyUpload, UploadTooLarge, InvalidAttachment) as exc:
        raise HTTPException(415, str(exc)) from exc
    checksum = sha256(content).hexdigest()
    existing = next((a for a in expense.attachments if a.checksum_sha256 == checksum), None)
    if existing:
        return {"id": str(existing.id), "filename": existing.filename}
    if content_type == "application/xml":
        if expense.document_type != "factura":
            raise HTTPException(415, "El vale o recibo debe ser PDF.")
        try:
            parsed = parse_cfdi_xml(content)
        except CfdiParseError as exc:
            raise HTTPException(422, str(exc)) from exc
        validation = validate_cfdi_for_expense(
            parsed,
            SimpleNamespace(amount=expense.amount, currency="MXN"),
            expected_receiver_rfc=settings.cfdi_receiver_rfc,
        )
        if not validation.is_valid:
            raise HTTPException(
                422,
                "\n".join(
                    issue.message for issue in validation.issues if issue.severity == "error"
                ),
            )
        if normalize_cfdi_uuid(parsed.uuid) != expense.cfdi_uuid:
            raise HTTPException(409, "El Folio Fiscal del XML no coincide con el gasto.")
        ocr_data = validation.model_dump(mode="json")
    else:
        if content_type != "application/pdf":
            raise HTTPException(415, "El comprobante debe ser PDF.")
        result = _ocr_result_from_preview_token(
            ocr_preview_token,
            checksum_sha256=checksum,
            settings=settings,
            db=db,
        )
        if result is None:
            await file.seek(0)
            preview = await _preview_invoice_ocr(file, settings, expense.document_type, db)
            result = _ocr_result_from_preview_token(
                preview.verification_token,
                checksum_sha256=checksum,
                settings=settings,
                db=db,
            )
        if result is None or not result.raw_text.strip():
            raise HTTPException(409, "No se pudo leer el documento.")
        ocr_data = jsonable_encoder(
            {
                "raw_text": result.raw_text,
                "raw_response": result.raw_response,
                "extracted_total": result.extracted_total,
                "extracted_date": result.extracted_date,
                "suggested_cfdi_uuid": result.suggested_cfdi_uuid,
            }
        )
        if expense.document_type == "factura":
            receiver = assess_invoice_receiver(
                result.raw_text,
                expected_name=settings.invoice_ocr_receiver_name,
                expected_rfc=settings.invoice_ocr_receiver_rfc,
            )
            ocr_data["receiver_validation"] = receiver
            if receiver["missing_fields"]:
                raise HTTPException(
                    409,
                    expected_invoice_receiver_message(
                        receiver["missing_fields"],
                        expected_name=settings.invoice_ocr_receiver_name,
                        expected_rfc=settings.invoice_ocr_receiver_rfc,
                    ),
                )
    # OCR may commit a standalone extraction. Recheck the draft under its row lock afterwards.
    db.expire_all()
    expense = get_expense(db, expense_id, actor, edit=True)
    existing = next((a for a in expense.attachments if a.checksum_sha256 == checksum), None)
    if existing:
        return {"id": str(existing.id), "filename": existing.filename}
    storage = StorageService(settings.upload_dir / "extemporaneos", settings.max_upload_bytes)
    stored = storage.save_bytes(content, filename=file.filename or "upload", expense_id=expense.id)
    attachment = HistoricalAttachment(
        expense=expense,
        filename=stored.filename,
        storage_path=stored.storage_path,
        content_type=content_type,
        checksum_sha256=checksum,
        size_bytes=stored.size_bytes,
        ocr_data=ocr_data,
    )
    try:
        db.add(attachment)
        audit_event(
            db,
            expense.request,
            actor,
            "historical_document_uploaded",
            f"Comprobante validado y guardado: {stored.filename}.",
            expense=expense,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        storage.delete(stored.storage_path)
        duplicate = db.scalar(
            select(HistoricalAttachment).where(
                HistoricalAttachment.expense_id == expense_id,
                HistoricalAttachment.checksum_sha256 == checksum,
            )
        )
        if duplicate:
            return {"id": str(duplicate.id), "filename": duplicate.filename}
        raise HTTPException(409, "El comprobante cambió. Reintenta la carga.") from exc
    except Exception:
        db.rollback()
        storage.delete(stored.storage_path)
        raise
    return {"id": str(attachment.id), "filename": attachment.filename}


def document_path(attachment: HistoricalAttachment, settings: Settings) -> Path:
    root = (settings.upload_dir / "extemporaneos").resolve()
    path = (root / attachment.storage_path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "Comprobante no encontrado.")
    return path


@router.get("/attachments/{attachment_id}/download/me")
def download_document(attachment_id: UUID, actor: Actor, db: Database, settings: Configuration):
    attachment = db.get(HistoricalAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(404, "Comprobante no encontrado.")
    expense = get_expense(db, attachment.expense_id, actor)
    audit_event(
        db,
        expense.request,
        actor,
        "historical_document_viewed",
        f"Comprobante consultado: {attachment.filename}.",
        expense=expense,
    )
    db.commit()
    return FileResponse(
        document_path(attachment, settings),
        media_type=attachment.content_type,
        filename=attachment.filename,
    )


@router.get("/{request_id}/invoices.zip/me")
def download_zip(request_id: UUID, actor: Actor, db: Database, settings: Configuration):
    request = get_request(db, request_id, actor)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for index, expense in enumerate((e for e in request.expenses if e.removed_at is None), 1):
            for number, attachment in enumerate(expense.attachments, 1):
                archive.write(
                    document_path(attachment, settings),
                    f"{index:03d}-{number}-{attachment.filename}",
                )
    audit_event(
        db,
        request,
        actor,
        "historical_zip_downloaded",
        "Comprobantes extemporáneos descargados en ZIP.",
    )
    db.commit()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(str(request.folio or request.id) + '-comprobantes.zip', safe='')}",
        },
    )


@router.get("/{request_id}/events/me")
def list_events(request_id: UUID, actor: Actor, db: Database, offset: int = 0, limit: int = 200):
    get_request(db, request_id, actor)
    if offset < 0 or not 1 <= limit <= 200:
        raise HTTPException(422, "Paginación inválida.")
    statement = select(AuditLog).where(
        AuditLog.event_payload["historical_request_id"].as_string() == str(request_id),
    )
    if actor.role not in {
        UserRole.admin,
        UserRole.accountant,
        UserRole.accounting_manager,
        UserRole.treasury,
        UserRole.director,
    }:
        statement = statement.where(
            (AuditLog.action != "expense_observation_added")
            | AuditLog.event_payload["is_initial_observation"].as_boolean().is_(True)
        )
    events = db.scalars(
        statement.order_by(AuditLog.created_at, AuditLog.id).offset(offset).limit(limit)
    )
    return [event_payload(event) for event in events]


@router.post("/{request_id}/events/me", status_code=201)
def capture_event(request_id: UUID, data: HistoricalEventCreate, actor: Actor, db: Database):
    request = get_request(db, request_id, actor, edit=data.action != "click")
    payload = data.model_dump(mode="json", exclude_none=True)
    label = data.field or data.label or data.action
    message = data.message or (f"{label}: {data.value}" if data.value is not None else label)
    event = audit_event(
        db,
        request,
        actor,
        f"historical_capture_{data.action}",
        message,
        event_id=data.event_id,
        payload=payload,
    )
    db.commit()
    return event_payload(event)


@router.post("/expenses/{expense_id}/observations/me", status_code=201)
def add_observation(
    expense_id: UUID, data: HistoricalObservationCreate, actor: Actor, db: Database
):
    expense = get_expense(db, expense_id, actor, edit=True)
    note = data.note.strip()
    if not note:
        raise HTTPException(422, "Escribe una observación.")
    event = audit_event(
        db,
        expense.request,
        actor,
        "expense_observation_added",
        note,
        expense=expense,
        event_id=data.event_id,
    )
    db.commit()
    return event_payload(event)
