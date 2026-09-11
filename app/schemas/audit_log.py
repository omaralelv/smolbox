from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
