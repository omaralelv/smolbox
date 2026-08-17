from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
    from app.models.audit_log import AuditLog
    from app.models.expense import Expense
    from app.models.payment import Payment
    from app.models.period import Period
    from app.models.store import Store


class ReimbursementRequestStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    authorization_review = "authorization_review"
    authorized = "authorized"
    under_accounting_review = "under_accounting_review"
    correction_required = "correction_required"
    accounting_reviewed = "accounting_reviewed"
    accounting_approved = "accounting_approved"
    accounting_manager_review = "accounting_manager_review"
    accounting_manager_approved = "accounting_manager_approved"
    treasury_review = "treasury_review"
    direction_review = "direction_review"
    direction_approved = "direction_approved"
    approved_for_payment = "approved_for_payment"
    paid = "paid"
    closed = "closed"
    rejected = "rejected"


class ReimbursementRequest(Base):
    __tablename__ = "reimbursement_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folio: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True, index=True)
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
    authorization_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accounting_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accounting_manager_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    treasury_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    direction_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    direction_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sap_policy_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sap_policy_generated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sap_policy_reference: Mapped[str | None] = mapped_column(String(120))
    sap_policy_payload: Mapped[dict | None] = mapped_column(JSON)
    approved_for_payment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correction_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correction_requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    correction_return_status: Mapped[ReimbursementRequestStatus | None] = mapped_column(
        Enum(ReimbursementRequestStatus, name="reimbursement_request_status"),
        nullable=True,
    )
    correction_reason: Mapped[str | None] = mapped_column(Text)

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
    payments: Mapped[list[Payment]] = relationship(
        back_populates="reimbursement_request",
        cascade="all, delete-orphan",
    )
