from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.expense import Expense


class OcrExtractionStatus(str, enum.Enum):
    succeeded = "succeeded"
    failed = "failed"


class OcrExtraction(Base):
    __tablename__ = "ocr_extractions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attachments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(60), nullable=False, default="aws_textract")
    status: Mapped[OcrExtractionStatus] = mapped_column(
        Enum(OcrExtractionStatus, name="ocr_extraction_status"),
        nullable=False,
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    extracted_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    extracted_date: Mapped[date | None] = mapped_column(Date)
    extracted_supplier: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    attachment: Mapped[Attachment] = relationship(back_populates="ocr_extraction")
    expense: Mapped[Expense | None] = relationship()
