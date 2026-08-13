from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.models.user import User
from app.schemas.attachment import AttachmentRead
from app.services.permissions import user_can_transition_store_request

router = APIRouter()


@router.get("/{attachment_id}", response_model=AttachmentRead)
def get_attachment(
    attachment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return attachment


@router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    upload_root = settings.upload_dir.resolve()
    file_path = (upload_root / Path(attachment.storage_path)).resolve()
    if not _is_relative_to(file_path, upload_root) or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found on disk",
        )

    return FileResponse(
        file_path,
        media_type=attachment.content_type,
        filename=attachment.filename,
    )


@router.get("/{attachment_id}/download/me")
def download_attachment_as_current_user(
    attachment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    store_id = _attachment_store_id(db, attachment)
    if store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ATTACHMENT_NOT_SCOPED",
                "message": "Attachment is not attached to a store reimbursement request",
            },
        )
    if not user_can_transition_store_request(db, current_user, store_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the attachment store",
            },
        )

    return _file_response(attachment, settings)


def _file_response(attachment: Attachment, settings: Settings) -> FileResponse:
    upload_root = settings.upload_dir.resolve()
    file_path = (upload_root / Path(attachment.storage_path)).resolve()
    if not _is_relative_to(file_path, upload_root) or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found on disk",
        )

    return FileResponse(
        file_path,
        media_type=attachment.content_type,
        filename=attachment.filename,
    )


def _attachment_store_id(db: Session, attachment: Attachment) -> UUID | None:
    if attachment.reimbursement_request_id is not None:
        return db.scalar(
            select(ReimbursementRequest.store_id).where(
                ReimbursementRequest.id == attachment.reimbursement_request_id
            )
        )
    if attachment.expense_id is None:
        return None
    return db.scalar(
        select(ReimbursementRequest.store_id)
        .join(Expense, Expense.reimbursement_request_id == ReimbursementRequest.id)
        .where(Expense.id == attachment.expense_id)
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
