from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense
from app.models.period import Period, PeriodStatus
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store import Store
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.schemas.audit_log import AuditLogRead
from app.schemas.reimbursement_request import (
    ReimbursementRequestCreate,
    ReimbursementRequestRead,
    ReimbursementRequestTransition,
    ReimbursementValidationSummary,
)
from app.services.file_validation import InvalidAttachment, detect_attachment_content_type
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.storage import (
    EmptyUpload,
    StorageService,
    UploadTooLarge,
    read_upload_limited,
)
from app.services.workflow import WorkflowTransitionError, transition_reimbursement_request

router = APIRouter()


@router.post("/", response_model=ReimbursementRequestRead, status_code=status.HTTP_201_CREATED)
def create_reimbursement_request(
    request_in: ReimbursementRequestCreate,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    store = db.get(Store, request_in.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    period = db.get(Period, request_in.period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    if period.status == PeriodStatus.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "PERIOD_CLOSED", "message": "The reimbursement period is closed"},
        )

    duplicate = db.scalar(
        select(ReimbursementRequest.id).where(
            ReimbursementRequest.store_id == request_in.store_id,
            ReimbursementRequest.period_id == request_in.period_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_REIMBURSEMENT_REQUEST",
                "message": "A request already exists for this store and period",
            },
        )

    reimbursement_request = ReimbursementRequest(**request_in.model_dump())
    db.add(reimbursement_request)
    try:
        db.flush()
        db.add(
            AuditLog(
                reimbursement_request_id=reimbursement_request.id,
                actor_type=AuditActorType.system,
                action="request_created",
                to_status=reimbursement_request.status.value,
                message="Reimbursement request created.",
            )
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_REIMBURSEMENT_REQUEST",
                "message": "A request already exists for this store and period",
            },
        ) from exc
    db.refresh(reimbursement_request)
    return reimbursement_request


@router.get("/", response_model=list[ReimbursementRequestRead])
def list_reimbursement_requests(
    db: Annotated[Session, Depends(get_db)],
    store_id: UUID | None = None,
    period_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ReimbursementRequest]:
    statement = (
        select(ReimbursementRequest)
        .order_by(ReimbursementRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if store_id is not None:
        statement = statement.where(ReimbursementRequest.store_id == store_id)
    if period_id is not None:
        statement = statement.where(ReimbursementRequest.period_id == period_id)
    return list(db.scalars(statement))


@router.get("/{request_id}", response_model=ReimbursementRequestRead)
def get_reimbursement_request(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    return reimbursement_request


@router.get("/{request_id}/validation-summary", response_model=ReimbursementValidationSummary)
def get_reimbursement_validation_summary(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementValidationSummary:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        )
        .where(ReimbursementRequest.id == request_id)
    )
    reimbursement_request = db.scalars(statement).first()
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )
    return summarize_reimbursement_request(reimbursement_request)


@router.post("/{request_id}/transition", response_model=ReimbursementRequestRead)
def transition_request(
    request_id: UUID,
    transition_in: ReimbursementRequestTransition,
    db: Annotated[Session, Depends(get_db)],
) -> ReimbursementRequest:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.period),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.cfdi_validations),
        )
        .where(ReimbursementRequest.id == request_id)
    )
    reimbursement_request = db.scalars(statement).first()
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    actor = db.get(User, transition_in.actor_user_id)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Actor user not found")

    summary = summarize_reimbursement_request(reimbursement_request)
    try:
        from_status, to_status = transition_reimbursement_request(
            reimbursement_request,
            actor=actor,
            target_status=transition_in.target_status,
            summary=summary,
        )
    except WorkflowTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVALID_WORKFLOW_TRANSITION", "message": str(exc)},
        ) from exc

    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_user_id=actor.id,
            actor_type=AuditActorType.user,
            action="request_status_changed",
            from_status=from_status.value,
            to_status=to_status.value,
            message=transition_in.note,
            event_payload={
                "ready_for_submission": summary.ready_for_submission,
                "ready_for_accounting_approval": summary.ready_for_accounting_approval,
            },
        )
    )
    db.commit()
    db.refresh(reimbursement_request)
    return reimbursement_request


@router.get("/{request_id}/audit-events", response_model=list[AuditLogRead])
def list_reimbursement_request_audit_events(
    request_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditLog]:
    if db.get(ReimbursementRequest, request_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    statement = (
        select(AuditLog)
        .where(AuditLog.reimbursement_request_id == request_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement))


@router.post(
    "/{request_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reimbursement_request_attachment(
    request_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    attachment_type: Annotated[AttachmentType, Form()] = AttachmentType.cash_box_format,
) -> Attachment:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    if attachment_type != AttachmentType.cash_box_format:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Request-level attachments must use the cash_box_format type",
        )

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    try:
        content = await read_upload_limited(file, settings.max_upload_bytes)
    except EmptyUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc

    try:
        content_type = detect_attachment_content_type(
            file.filename or "upload",
            content,
            attachment_type,
        )
    except InvalidAttachment as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc

    stored = storage.save_bytes(
        content,
        filename=file.filename or "upload",
        reimbursement_request_id=request_id,
    )
    attachment = Attachment(
        reimbursement_request_id=reimbursement_request.id,
        attachment_type=attachment_type,
        filename=stored.filename,
        content_type=content_type,
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    db.add(attachment)
    db.add(
        AuditLog(
            reimbursement_request_id=reimbursement_request.id,
            actor_type=AuditActorType.system,
            action="request_attachment_uploaded",
            message=f"Attachment uploaded: {stored.filename}",
            event_payload={
                "attachment_type": attachment_type.value,
                "size_bytes": stored.size_bytes,
                "checksum_sha256": stored.checksum_sha256,
            },
        )
    )
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(stored.storage_path)
        raise
    db.refresh(attachment)
    return attachment
