from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.reimbursement_request import ReimbursementRequest


class PeriodStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class Period(Base):
    __tablename__ = "periods"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PeriodStatus] = mapped_column(
        Enum(PeriodStatus, name="period_status"),
        default=PeriodStatus.open,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    expenses: Mapped[list[Expense]] = relationship(back_populates="period")
    reimbursement_requests: Mapped[list[ReimbursementRequest]] = relationship(
        back_populates="period",
    )
