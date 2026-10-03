from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.user import UserRole


class StoreUserAssignmentCreate(BaseModel):
    user_id: UUID
    role: UserRole
    is_active: bool = True


class StoreUserAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    user_id: UUID
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
