from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.reimbursement_request import ReimbursementRequestStatus


class ReimbursementRequestBase(BaseModel):
    store_id: UUID
    period_id: UUID
    reported_total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    previous_reimbursement_starts_on: date | None = None
    previous_reimbursement_ends_on: date | None = None
    previous_reimbursement_amount: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )
    notes: str | None = None

    @model_validator(mode="after")
    def validate_previous_reimbursement_dates(self) -> "ReimbursementRequestBase":
        starts_on = self.previous_reimbursement_starts_on
        ends_on = self.previous_reimbursement_ends_on
        if starts_on and ends_on and ends_on < starts_on:
            raise ValueError(
                "previous_reimbursement_ends_on must be on or after "
                "previous_reimbursement_starts_on"
            )
        return self


class ReimbursementRequestCreate(ReimbursementRequestBase):
    pass


class ReimbursementRequestRead(ReimbursementRequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ReimbursementRequestStatus
    created_at: datetime
    updated_at: datetime


class CategoryTotal(BaseModel):
    category: str
    total: Decimal
    expense_count: int


class ReimbursementValidationIssue(BaseModel):
    code: str
    message: str
    severity: str = "error"


class ReimbursementValidationSummary(BaseModel):
    request_id: UUID
    reported_total: Decimal | None
    calculated_total: Decimal
    difference: Decimal | None
    expense_count: int
    category_totals: list[CategoryTotal]
    missing_receipt_expense_ids: list[UUID]
    missing_cfdi_expense_ids: list[UUID]
    is_balanced: bool
    issues: list[ReimbursementValidationIssue]
