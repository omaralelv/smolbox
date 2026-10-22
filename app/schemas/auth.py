from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.user import UserRole
from app.schemas.period import PeriodRead
from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not email:
            raise ValueError("Email cannot be blank")
        return email


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class StoreContextRead(BaseModel):
    id: UUID
    code: str
    name: str
    contact_email: str | None = None
    assigned_accountant: str | None = None
    manager_name: str | None = None
    bank_account: str | None = None
    state_region: str | None = None
    assignment_role: UserRole | None = None
    is_active_assignment: bool = True


class AuthContextRead(BaseModel):
    user: UserRead
    stores: list[StoreContextRead] = Field(default_factory=list)
    active_store: StoreContextRead | None = None
    current_period: PeriodRead | None = None
