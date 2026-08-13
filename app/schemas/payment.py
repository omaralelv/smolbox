from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.payment import PaymentStatus


class PaymentCreate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    payment_method: str | None = Field(default="transfer", max_length=80)
    reference: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reimbursement_request_id: UUID
    amount: Decimal
    currency: str
    payment_method: str | None
    reference: str
    note: str | None
    status: PaymentStatus
    paid_at: datetime
    paid_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
