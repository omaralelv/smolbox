from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import UserRole

if TYPE_CHECKING:
    from app.models.reimbursement_request import ReimbursementRequest
    from app.models.user import User


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    assigned_accountant: Mapped[str | None] = mapped_column(String(160))
    manager_name: Mapped[str | None] = mapped_column(String(160))
    bank_account: Mapped[str | None] = mapped_column(String(80))
    state_region: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    reimbursement_requests: Mapped[list[ReimbursementRequest]] = relationship(
        back_populates="store",
    )
    user_assignments: Mapped[list[StoreUserAssignment]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
    )


class StoreUserAssignment(Base):
    __tablename__ = "store_user_assignments"
    __table_args__ = (
        UniqueConstraint("store_id", "user_id", name="uq_store_user_assignments_store_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    store: Mapped[Store] = relationship(back_populates="user_assignments")
    user: Mapped[User] = relationship(back_populates="store_assignments")
