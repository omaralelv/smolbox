from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.store import Store


class HistoricalRequest(Base):
    """Informational archive; deliberately has no reimbursement period or workflow."""

    __tablename__ = "historical_requests"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'paid')", name="ck_historical_status"),
        CheckConstraint(
            "(status = 'draft' AND registered_at IS NULL AND folio IS NULL) OR "
            "(status = 'paid' AND registered_at IS NOT NULL AND folio IS NOT NULL)",
            name="ck_historical_registration",
        ),
        Index(
            "uq_historical_open_draft",
            "store_id",
            "created_by_user_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"), index=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    folio: Mapped[str | None] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    store: Mapped[Store] = relationship()
    expenses: Mapped[list[HistoricalExpense]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class HistoricalExpense(Base):
    __tablename__ = "historical_expenses"
    __table_args__ = (
        Index(
            "uq_historical_active_uuid",
            "cfdi_uuid",
            unique=True,
            postgresql_where=text("removed_at IS NULL AND cfdi_uuid IS NOT NULL"),
            sqlite_where=text("removed_at IS NULL AND cfdi_uuid IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("historical_requests.id"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    spent_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    document_type: Mapped[str] = mapped_column(String(20))
    cfdi_uuid: Mapped[str | None] = mapped_column(String(36), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    fiscal_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request: Mapped[HistoricalRequest] = relationship(back_populates="expenses")
    attachments: Mapped[list[HistoricalAttachment]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class HistoricalAttachment(Base):
    __tablename__ = "historical_attachments"
    __table_args__ = (
        UniqueConstraint("expense_id", "checksum_sha256", name="uq_historical_attachment_checksum"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    expense_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("historical_expenses.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    storage_path: Mapped[str] = mapped_column(String(500))
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column()
    ocr_data: Mapped[dict | None] = mapped_column(JSON)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expense: Mapped[HistoricalExpense] = relationship(back_populates="attachments")
