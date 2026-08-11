from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentRead

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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
