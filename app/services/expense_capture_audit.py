from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.models.user import User
from app.schemas.frontend import FrontendCaptureEventCreate
from app.services.permissions import user_has_store_assignment

CAPTURE_STARTED = "expense_capture_started"
FIELD_LABELS = {
    "category": "categoría",
    "amount": "monto",
    "date": "fecha",
    "folio": "folio",
    "authorization_area": "área que autoriza",
    "document_type": "tipo de documento",
    "observations": "observaciones",
}


def get_capture(
    db: Session, capture_id: UUID, actor: User, *, require_open: bool = True
) -> AuditLog:
    # The initial audit event is the durable capture anchor, even before a request exists.
    capture = db.scalar(select(AuditLog).where(AuditLog.id == capture_id).with_for_update())
    if capture is None or capture.action != CAPTURE_STARTED or capture.actor_user_id != actor.id:
        raise HTTPException(status_code=404, detail="Captura no encontrada.")
    store_id = UUID(capture.event_payload["store_id"])
    if not user_has_store_assignment(db, actor, store_id):
        raise HTTPException(status_code=403, detail="No tienes acceso a la tienda de esta captura.")
    if require_open:
        cancelled = db.scalar(
            select(AuditLog.id).where(
                AuditLog.action.in_({"expense_capture_cancelled", "expense_capture_added"}),
                AuditLog.event_payload["capture_id"].as_string() == str(capture_id),
            )
        )
        if capture.expense_id is not None or cancelled is not None:
            raise HTTPException(status_code=409, detail="La captura ya fue añadida o cancelada.")
    return capture


def add_capture_event(
    db: Session,
    capture: AuditLog,
    actor: User,
    *,
    action: str,
    message: str,
    payload: dict | None = None,
    event_id: UUID | None = None,
) -> AuditLog:
    event = AuditLog(
        reimbursement_request_id=capture.reimbursement_request_id,
        expense_id=capture.expense_id,
        actor_user_id=actor.id,
        actor_type=AuditActorType.user,
        action=action,
        message=message,
        event_payload={
            "capture_id": str(capture.id),
            "store_id": capture.event_payload["store_id"],
            "store_code": capture.event_payload["store_code"],
            "actor_role": actor.role.value,
            "actor_name": actor.full_name,
            **(payload or {}),
        },
        created_at=datetime.now(UTC),
    )
    if event_id is not None:
        event.id = event_id
    db.add(event)
    return event


def capture_event_message(event: FrontendCaptureEventCreate) -> str:
    if event.action == "click":
        if not event.label or not event.label.strip():
            raise HTTPException(
                status_code=422, detail="El movimiento necesita el nombre del botón."
            )
        return f"Click registrado durante captura: {event.label.strip()}."
    if event.action == "field_changed":
        if event.field is None:
            raise HTTPException(status_code=422, detail="El movimiento necesita el campo editado.")
        previous, value = event.previous_value or "Sin capturar", event.value or "Sin capturar"
        return f"Cambio de {FIELD_LABELS[event.field]} de {previous} a {value} durante captura."
    if event.action == "file_selected":
        return (
            f"Documento seleccionado ({event.document_type or 'documento'}): {event.filename}. "
            "Todavía no guardado como comprobante."
            if event.filename
            else "Documento retirado de la captura."
        )
    labels = {
        "validation_started": "Validación del gasto iniciada desde el formulario.",
        "validation_completed": "Validación del formulario completada.",
        "validation_failed": "Validación del formulario no completada.",
        "folio_confirmed": f"Folio confirmado durante captura: {event.value or 'Sin capturar'}.",
        "cancelled": "Captura cancelada sin añadir el gasto.",
        "left": "Se salió de la captura sin añadir el gasto.",
    }
    return " ".join(part for part in [labels[event.action], event.message] if part)


def link_capture_to_expense(
    db: Session,
    capture_id: UUID | None,
    actor: User,
    request: ReimbursementRequest,
    expense: Expense,
) -> None:
    if capture_id is None:
        return
    capture = get_capture(db, capture_id, actor)
    if UUID(capture.event_payload["store_id"]) != request.store_id or (
        capture.reimbursement_request_id is not None
        and capture.reimbursement_request_id != request.id
    ):
        raise HTTPException(
            status_code=409, detail="La captura pertenece a otra solicitud o tienda."
        )
    events = db.scalars(
        select(AuditLog).where(AuditLog.event_payload["capture_id"].as_string() == str(capture_id))
    )
    for event in events:
        event.reimbursement_request_id = request.id
        event.expense_id = expense.id
    capture.reimbursement_request_id = request.id
    capture.expense_id = expense.id
    add_capture_event(
        db,
        capture,
        actor,
        action="expense_capture_added",
        message=f"Captura añadida a la solicitud como Gasto - {expense.category}.",
    )
