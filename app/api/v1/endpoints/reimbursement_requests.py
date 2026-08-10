from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment, AttachmentType
from app.models.expense import Expense
from app.models.period import Period
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store import Store
from app.schemas.attachment import AttachmentRead
from app.schemas.reimbursement_request import (
    ReimbursementRequestCreate,
    ReimbursementRequestRead,
    ReimbursementValidationSummary,
)
from app.services.reimbursement_validation import summarize_reimbursement_request
from app.services.storage import EmptyUpload, StorageService, UploadTooLarge


router = APIRouter()


@router.post("/", response_model=ReimbursementRequestRead, status_code=status.HTTP_201_CREATED)
def create_reimbursement_request(
    request_in: ReimbursementRequestCreate,
    db: Session = Depends(get_db),
) -> ReimbursementRequest:
    store = db.get(Store, request_in.store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    period = db.get(Period, request_in.period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")

    reimbursement_request = ReimbursementRequest(**request_in.model_dump())
    db.add(reimbursement_request)
    db.commit()
    db.refresh(reimbursement_request)
    return reimbursement_request


@router.get("/", response_model=list[ReimbursementRequestRead])
def list_reimbursement_requests(
    store_id: UUID | None = None,
    period_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
) -> ReimbursementValidationSummary:
    statement = (
        select(ReimbursementRequest)
        .options(
            selectinload(ReimbursementRequest.expenses).selectinload(Expense.attachments),
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


@router.post(
    "/{request_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reimbursement_request_attachment(
    request_id: UUID,
    attachment_type: AttachmentType = Form(default=AttachmentType.cash_box_format),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Attachment:
    reimbursement_request = db.get(ReimbursementRequest, request_id)
    if reimbursement_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reimbursement request not found",
        )

    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.allowed_attachment_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {content_type}",
        )

    storage = StorageService(settings.upload_dir, settings.max_upload_bytes)
    try:
        stored = await storage.save_upload(file, reimbursement_request_id=request_id)
    except EmptyUpload as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc

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
    db.commit()
    db.refresh(attachment)
    return attachment
