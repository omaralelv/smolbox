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
from app.models.expense import Expense, ExpenseStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.schemas.attachment import AttachmentRead
from app.services.authorization_areas import (
    expense_is_visible_to_authorizer,
    request_is_visible_to_authorizer,
)
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

    request = _attachment_request(db, attachment)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ATTACHMENT_NOT_SCOPED",
                "message": "Attachment is not attached to a store reimbursement request",
            },
        )
    is_authorizer = current_user.role == UserRole.authorizer
    authorizer_can_view_request = is_authorizer and request_is_visible_to_authorizer(
        request, current_user, db,
    )
    area_scoped_document = (
        authorizer_can_view_request
        and attachment.expense_id is not None
        and request.status in {
            ReimbursementRequestStatus.submitted,
            ReimbursementRequestStatus.authorization_review,
        }
    )
    if not user_can_transition_store_request(db, current_user, request.store_id) and not area_scoped_document:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "STORE_ASSIGNMENT_REQUIRED",
                "message": "Actor must be assigned to the attachment store",
            },
        )

    if is_authorizer and (
        not authorizer_can_view_request
        or (
            attachment.expense is not None
            and not _expense_document_is_visible(attachment.expense, request, current_user, db)
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "AUTHORIZATION_AREA_FORBIDDEN",
                "message": "El comprobante no pertenece a un gasto visible para tu \u00e1rea de autorizaci\u00f3n.",
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


def _attachment_request(db: Session, attachment: Attachment) -> ReimbursementRequest | None:
    if attachment.reimbursement_request_id is not None:
        return db.get(ReimbursementRequest, attachment.reimbursement_request_id)
    if attachment.expense_id is None:
        return None
    return db.scalar(
        select(ReimbursementRequest)
        .join(Expense, Expense.reimbursement_request_id == ReimbursementRequest.id)
        .where(Expense.id == attachment.expense_id)
    )


def _expense_document_is_visible(
    expense: Expense,
    request: ReimbursementRequest,
    user: User,
    db: Session,
) -> bool:
    if expense.partition_parent_expense_id is not None and (
        expense.status in {ExpenseStatus.removed, ExpenseStatus.rejected}
        or expense.removed_at is not None
    ):
        return False

    # Active partitions display their parent's document and can belong to different areas.
    candidates = [
        child for child in expense.partition_children
        if child.reimbursement_request_id == request.id
        and child.status not in {ExpenseStatus.removed, ExpenseStatus.rejected}
        and child.removed_at is None
    ] or [expense]
    return any(
        expense_is_visible_to_authorizer(db, user, candidate, store_id=request.store_id)
        for candidate in candidates
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
