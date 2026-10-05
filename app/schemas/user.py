import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole
from app.schemas.store import StoreRead
from app.schemas.store_assignment import StoreUserAssignmentRead


class UserCreate(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole
    is_active: bool = True
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not email:
            raise ValueError("Email cannot be blank")
        return email


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=1, max_length=255)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip().lower()
        if not email:
            raise ValueError("Email cannot be blank")
        return email


class UserDelete(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        reason = " ".join(value.strip().split())
        if not reason:
            raise ValueError("Reason cannot be blank")
        return reason


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StoreUserCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=1, max_length=255)
    is_active: bool = True
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("code")
    @classmethod
    def normalize_store_code(cls, value: str) -> str:
        code = value.strip().upper()
        if not re.fullmatch(r"T\d{3}", code):
            raise ValueError("Store code must use the T### format")
        return code

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        full_name = value.strip()
        if not full_name:
            raise ValueError("Name cannot be blank")
        return full_name

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not email:
            raise ValueError("Email cannot be blank")
        return email


class StoreUserCreateResponse(BaseModel):
    store: StoreRead
    user: UserRead
    assignment: StoreUserAssignmentRead
