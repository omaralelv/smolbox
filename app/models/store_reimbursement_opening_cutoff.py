import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoreReimbursementOpeningCutoff(Base):
    __tablename__ = (
        "store_reimbursement_opening_cutoffs"
    )

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            name=(
                "uq_store_reimbursement_opening_cutoff"
            ),
        ),
        CheckConstraint(
            "ends_on >= starts_on",
            name="ck_opening_cutoff_dates",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "stores.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    starts_on: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    ends_on: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    reimbursed_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )