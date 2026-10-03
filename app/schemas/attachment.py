from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.attachment import AttachmentType
from app.models.ocr_extraction import OcrExtractionStatus


class OcrExtractionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attachment_id: UUID
    expense_id: UUID | None = None
    provider: str
    status: OcrExtractionStatus
    extracted_total: Decimal | None = None
    extracted_date: date | None = None
    extracted_supplier: str | None = None
    suggested_cfdi_uuid: str | None = None
    confidence: Decimal | None = None
    error_message: str | None = None
    created_at: datetime


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    expense_id: UUID | None = None
    reimbursement_request_id: UUID | None = None
    attachment_type: AttachmentType
    filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    uploaded_at: datetime
    ocr_extraction: OcrExtractionRead | None = None
