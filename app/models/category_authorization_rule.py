from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.authorization_area import AuthorizationArea


class CategoryAuthorizationRule(Base):
    __tablename__ = "category_authorization_rules"
    __table_args__ = (
        UniqueConstraint(
            "normalized_category",
            name="uq_category_authorization_rules_normalized_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    authorization_area_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("authorization_areas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    minimum_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    requires_authorization: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    authorization_area: Mapped[AuthorizationArea | None] = relationship()
