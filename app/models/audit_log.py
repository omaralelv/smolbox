from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.reimbursement_request import ReimbursementRequest
    from app.models.user import User


class AuditActorType(str, enum.Enum):
    system = "system"
    user = "user"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reimbursement_request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reimbursement_requests.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[AuditActorType] = mapped_column(
        Enum(AuditActorType, name="audit_actor_type"),
        default=AuditActorType.system,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(80))
    to_status: Mapped[str | None] = mapped_column(String(80))
    message: Mapped[str | None] = mapped_column(Text)
    event_payload: Mapped[dict[str, Any] | None] = mapped_column("payload", JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    reimbursement_request: Mapped[ReimbursementRequest | None] = relationship(
        back_populates="audit_events",
    )
    expense: Mapped[Expense | None] = relationship(back_populates="audit_events")
    actor_user: Mapped[User | None] = relationship(back_populates="audit_events")
