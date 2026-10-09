from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.audit_log import AuditActorType


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reimbursement_request_id: UUID | None = None
    expense_id: UUID | None = None
    actor_user_id: UUID | None = None
    actor_type: AuditActorType
    action: str
    from_status: str | None = None
    to_status: str | None = None
    message: str | None = None
    event_payload: dict[str, Any] | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def ensure_timestamp_timezone(cls, value: datetime) -> datetime:
        # SQLite returns naive timestamps; audit events are stored in UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class FrontendAuditLogRead(AuditLogRead):
    store_code: str | None = None
    request_folio: str | None = None
    actor_name: str | None = None
    actor_role: str | None = None
