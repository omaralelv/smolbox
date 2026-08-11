from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.audit_log import AuditLog
    from app.models.expense import Expense
    from app.models.period import Period
    from app.models.store import Store


class ReimbursementRequestStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    under_accounting_review = "under_accounting_review"
    correction_required = "correction_required"
    accounting_approved = "accounting_approved"
    treasury_review = "treasury_review"
    approved_for_payment = "approved_for_payment"
    paid = "paid"
    closed = "closed"
    rejected = "rejected"


class ReimbursementRequest(Base):
    __tablename__ = "reimbursement_requests"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "period_id",
            name="uq_reimbursement_requests_store_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reported_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    previous_reimbursement_starts_on: Mapped[date | None] = mapped_column(Date)
    previous_reimbursement_ends_on: Mapped[date | None] = mapped_column(Date)
    previous_reimbursement_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ReimbursementRequestStatus] = mapped_column(
        Enum(ReimbursementRequestStatus, name="reimbursement_request_status"),
        default=ReimbursementRequestStatus.draft,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accounting_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    treasury_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_for_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    store: Mapped[Store] = relationship(back_populates="reimbursement_requests")
    period: Mapped[Period] = relationship(back_populates="reimbursement_requests")
    expenses: Mapped[list[Expense]] = relationship(back_populates="reimbursement_request")
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="reimbursement_request",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    audit_events: Mapped[list[AuditLog]] = relationship(
        back_populates="reimbursement_request",
        cascade="all, delete-orphan",
    )
