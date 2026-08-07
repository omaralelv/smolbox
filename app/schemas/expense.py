from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.expense import ExpenseStatus


class ExpenseBase(BaseModel):
    period_id: UUID
    merchant: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    spent_on: date
    category: str | None = Field(default=None, max_length=120)
    description: str | None = None
    supplier_tax_id: str | None = Field(default=None, max_length=20)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("supplier_tax_id")
    @classmethod
    def normalize_tax_id(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseRead(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cfdi_uuid: str | None = None
    cfdi_issuer_rfc: str | None = None
    cfdi_receiver_rfc: str | None = None
    cfdi_total: Decimal | None = None
    cfdi_currency: str | None = None
    status: ExpenseStatus
    created_at: datetime
    updated_at: datetime
