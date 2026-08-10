from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.cfdi_validation import CfdiValidation
    from app.models.period import Period
    from app.models.reimbursement_request import ReimbursementRequest


class ExpenseStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reimbursement_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reimbursement_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MXN", nullable=False)
    spent_on: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    supplier_tax_id: Mapped[str | None] = mapped_column(String(20), index=True)
    cfdi_uuid: Mapped[str | None] = mapped_column(String(36), unique=True)
    cfdi_issuer_rfc: Mapped[str | None] = mapped_column(String(20))
    cfdi_receiver_rfc: Mapped[str | None] = mapped_column(String(20))
    cfdi_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cfdi_currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[ExpenseStatus] = mapped_column(
        Enum(ExpenseStatus, name="expense_status"),
        default=ExpenseStatus.draft,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    period: Mapped[Period] = relationship(back_populates="expenses")
    reimbursement_request: Mapped[ReimbursementRequest | None] = relationship(
        back_populates="expenses",
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="expense",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    cfdi_validations: Mapped[list[CfdiValidation]] = relationship(
        back_populates="expense",
        cascade="all, delete-orphan",
    )
