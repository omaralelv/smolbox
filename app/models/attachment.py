from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AttachmentType(str, enum.Enum):
    receipt = "receipt"
    cfdi_xml = "cfdi_xml"
    cash_box_format = "cash_box_format"
    other = "other"


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "(expense_id IS NOT NULL) <> (reimbursement_request_id IS NOT NULL)",
            name="ck_attachments_single_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    reimbursement_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reimbursement_requests.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    attachment_type: Mapped[AttachmentType] = mapped_column(
        Enum(AttachmentType, name="attachment_type"),
        default=AttachmentType.receipt,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    expense: Mapped["Expense | None"] = relationship(back_populates="attachments")
    reimbursement_request: Mapped["ReimbursementRequest | None"] = relationship(
        back_populates="attachments",
    )
