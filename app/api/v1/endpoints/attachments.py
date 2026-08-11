from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense
from app.schemas.attachment import AttachmentRead
from app.services.file_validation import InvalidAttachment, detect_attachment_content_type
from app.services.storage import (
    EmptyUpload,
    StorageService,
    UploadTooLarge,
    read_upload_limited,
)

router = APIRouter()


@router.post(
    "/{expense_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    expense_id: UUID,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    attachment_type: Annotated[AttachmentType, Form()] = AttachmentType.receipt,
) -> Attachment:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")

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
        expense_id=expense_id,
    )
    attachment = Attachment(
        expense_id=expense.id,
        attachment_type=attachment_type,
        filename=stored.filename,
        content_type=content_type,
        storage_path=stored.storage_path,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.checksum_sha256,
    )
    db.add(attachment)
    if expense.reimbursement_request_id is not None:
        db.add(
            AuditLog(
                reimbursement_request_id=expense.reimbursement_request_id,
                expense_id=expense.id,
                actor_type=AuditActorType.system,
                action="expense_attachment_uploaded",
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
