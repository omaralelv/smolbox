from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StoreBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    contact_email: str | None = Field(default=None, max_length=255)
    assigned_accountant: str | None = Field(default=None, max_length=160)
    manager_name: str | None = Field(default=None, max_length=160)
    bank_account: str | None = Field(default=None, max_length=80)
    state_region: str | None = Field(default=None, max_length=120)
    petty_cash_fund: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=12, decimal_places=2)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        code = value.strip()
        if not code:
            raise ValueError("Store code cannot be blank")
        return code

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip()
        return email or None


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_email: str | None = Field(default=None, max_length=255)
    assigned_accountant: str | None = Field(default=None, max_length=160)
    manager_name: str | None = Field(default=None, max_length=160)
    bank_account: str | None = Field(default=None, max_length=80)
    state_region: str | None = Field(default=None, max_length=120)
    petty_cash_fund: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.strip()
        if not code:
            raise ValueError("Store code cannot be blank")
        return code

    @field_validator("contact_email")
    @classmethod
    def normalize_contact_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        email = value.strip()
        return email or None


class StoreRead(StoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
