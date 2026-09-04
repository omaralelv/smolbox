from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BusinessRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str
    value: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BusinessRuleUpdate(BaseModel):
    value: dict | None = None
    is_active: bool | None = None
    description: str | None = Field(default=None, min_length=1, max_length=2000)
