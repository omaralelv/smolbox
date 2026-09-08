from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense
from app.models.ocr_extraction import OcrExtraction, OcrExtractionStatus
from app.models.reimbursement_request import ReimbursementRequest
from app.schemas.attachment import AttachmentRead
from app.services.file_validation import InvalidAttachment, detect_attachment_content_type
from app.services.request_editability import is_request_editable
from app.services.storage import (
    EmptyUpload,
    StorageService,
    UploadTooLarge,
    read_upload_limited,
)
from app.services.textract_ocr import TextractOcrError, TextractOcrResult, TextractOcrService

router = APIRouter()

OCR_ATTACHMENT_TYPES = {AttachmentType.receipt, AttachmentType.cash_box_format}


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
    if expense.reimbursement_request is not None:
        _ensure_request_editable(
            expense.reimbursement_request,
            message="Attachments can only be uploaded while the request is draft or in correction.",
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
    try:
        db.add(attachment)
        db.flush()
        _maybe_extract_attachment_ocr(
            attachment,
            expense,
            content=content,
            settings=settings,
            db=db,
        )
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
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(stored.storage_path)
        raise
    db.refresh(attachment)
    return attachment


def _ensure_request_editable(reimbursement_request: ReimbursementRequest, *, message: str) -> None:
    if not is_request_editable(reimbursement_request):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REQUEST_NOT_EDITABLE",
                "message": message,
            },
        )


def _maybe_extract_attachment_ocr(
    attachment: Attachment,
    expense: Expense,
    *,
    content: bytes,
    settings: Settings,
    db: Session,
) -> None:
    if attachment.attachment_type not in OCR_ATTACHMENT_TYPES:
        return

    service = TextractOcrService(settings)
    if not service.is_enabled or not service.supports_content_type(attachment.content_type):
        return

    try:
        result = service.extract_expense(
            content,
            content_type=attachment.content_type,
            filename=attachment.filename,
        )
    except TextractOcrError as exc:
        db.add(
            OcrExtraction(
                attachment_id=attachment.id,
                expense_id=expense.id,
                status=OcrExtractionStatus.failed,
                error_message=str(exc),
            )
        )
        _add_ocr_audit_event(
            expense,
            action="expense_ocr_failed",
            message=str(exc),
            payload={"provider": "aws_textract"},
            db=db,
        )
        return

    if result is None:
        return

    db.add(
        OcrExtraction(
            attachment_id=attachment.id,
            expense_id=expense.id,
            status=OcrExtractionStatus.succeeded,
            raw_text=result.raw_text,
            extracted_total=result.extracted_total,
            extracted_date=result.extracted_date,
            extracted_supplier=result.extracted_supplier,
            confidence=result.confidence,
            raw_response=result.raw_response,
        )
    )
    _add_ocr_audit_event(
        expense,
        action="expense_ocr_extracted",
        message="OCR extracted with AWS Textract.",
        payload=_ocr_audit_payload(result),
        db=db,
    )


def _add_ocr_audit_event(
    expense: Expense,
    *,
    action: str,
    message: str,
    payload: dict[str, object],
    db: Session,
) -> None:
    if expense.reimbursement_request_id is None:
        return
    db.add(
        AuditLog(
            reimbursement_request_id=expense.reimbursement_request_id,
            expense_id=expense.id,
            actor_type=AuditActorType.system,
            action=action,
            message=message,
            event_payload=payload,
        )
    )


def _ocr_audit_payload(result: TextractOcrResult) -> dict[str, object]:
    return {
        "provider": "aws_textract",
        "extracted_total": str(result.extracted_total) if result.extracted_total else None,
        "extracted_date": result.extracted_date.isoformat() if result.extracted_date else None,
        "extracted_supplier": result.extracted_supplier,
        "confidence": str(result.confidence) if result.confidence else None,
    }
