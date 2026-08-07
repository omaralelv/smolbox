from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.attachment import AttachmentType


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    expense_id: UUID
    attachment_type: AttachmentType
    filename: str
    content_type: str
    storage_path: str
    size_bytes: int
    checksum_sha256: str
    uploaded_at: datetime
