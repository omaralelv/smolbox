from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.expense import ExpenseStatus


class ExpenseBase(BaseModel):
    period_id: UUID | None = None
    reimbursement_request_id: UUID | None = None
    merchant: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    spent_on: date
    category: str | None = Field(default=None, max_length=120)
    description: str | None = None
    supplier_tax_id: str | None = Field(default=None, max_length=20)
    requires_authorization: bool = False

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("supplier_tax_id")
    @classmethod
    def normalize_tax_id(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ExpenseCreate(ExpenseBase):
    @model_validator(mode="after")
    def validate_owner(self) -> "ExpenseCreate":
        if self.period_id is None and self.reimbursement_request_id is None:
            raise ValueError("period_id or reimbursement_request_id is required")
        return self


class ExpenseUpdate(BaseModel):
    merchant: str | None = Field(default=None, min_length=1, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    spent_on: date | None = None
    category: str | None = Field(default=None, max_length=120)
    description: str | None = None
    supplier_tax_id: str | None = Field(default=None, max_length=20)
    requires_authorization: bool | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("supplier_tax_id")
    @classmethod
    def normalize_tax_id(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class ExpenseRead(ExpenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_id: UUID
    cfdi_uuid: str | None = None
    cfdi_issuer_rfc: str | None = None
    cfdi_receiver_rfc: str | None = None
    cfdi_total: Decimal | None = None
    cfdi_currency: str | None = None
    authorized_at: datetime | None = None
    authorized_by_user_id: UUID | None = None
    authorization_note: str | None = None
    review_note: str | None = None
    removed_at: datetime | None = None
    removed_by_user_id: UUID | None = None
    removal_reason: str | None = None
    status: ExpenseStatus
    created_at: datetime
    updated_at: datetime


class ExpenseAuthorization(BaseModel):
    actor_user_id: UUID
    note: str | None = Field(default=None, max_length=1000)


class AuthenticatedExpenseAuthorization(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ExpenseRejection(BaseModel):
    actor_user_id: UUID
    reason: str = Field(min_length=1, max_length=1000)
    adjust_reported_total: bool = True


class AuthenticatedExpenseRejection(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    adjust_reported_total: bool = True


class ExpenseObservation(BaseModel):
    actor_user_id: UUID
    note: str = Field(min_length=1, max_length=1000)


class AuthenticatedExpenseObservation(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


class ExpenseReviewUpdate(ExpenseUpdate):
    actor_user_id: UUID
    note: str | None = Field(default=None, max_length=1000)


class AuthenticatedExpenseReviewUpdate(ExpenseUpdate):
    note: str | None = Field(default=None, max_length=1000)


class ExpenseRemoval(BaseModel):
    actor_user_id: UUID
    reason: str = Field(min_length=1, max_length=1000)
    adjust_reported_total: bool = True


class AuthenticatedExpenseRemoval(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    adjust_reported_total: bool = True
