from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.reimbursement_request import ReimbursementRequestStatus
from app.schemas.attachment import AttachmentRead
from app.schemas.audit_log import AuditLogRead
from app.schemas.cfdi import CfdiValidationRead
from app.schemas.expense import ExpenseRead
from app.schemas.payment import PaymentRead
from app.schemas.period import PeriodRead
from app.schemas.store import StoreRead


class ReimbursementRequestBase(BaseModel):
    folio: str | None = Field(default=None, max_length=80)
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


class ReimbursementRequestUpdate(BaseModel):
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


class ReimbursementRequestRead(ReimbursementRequestBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: ReimbursementRequestStatus
    submitted_at: datetime | None = None
    authorization_reviewed_at: datetime | None = None
    accounting_reviewed_at: datetime | None = None
    accounting_manager_reviewed_at: datetime | None = None
    treasury_reviewed_at: datetime | None = None
    direction_reviewed_at: datetime | None = None
    direction_approved_at: datetime | None = None
    sap_policy_generated_at: datetime | None = None
    sap_policy_generated_by_user_id: UUID | None = None
    sap_policy_reference: str | None = None
    sap_policy_payload: dict | None = None
    approved_for_payment_at: datetime | None = None
    paid_at: datetime | None = None
    closed_at: datetime | None = None
    correction_requested_at: datetime | None = None
    correction_requested_by_user_id: UUID | None = None
    correction_return_status: ReimbursementRequestStatus | None = None
    correction_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class ExpenseDetailRead(ExpenseRead):
    attachments: list[AttachmentRead] = Field(default_factory=list)
    current_cfdi_validation: CfdiValidationRead | None = None


class ReimbursementRequestQueueItemRead(ReimbursementRequestRead):
    store: StoreRead
    period: PeriodRead
    calculated_total: Decimal
    expense_count: int
    available_actions: list[str] = Field(default_factory=list)


class ReimbursementRequestDetailRead(ReimbursementRequestRead):
    store: StoreRead
    period: PeriodRead
    expenses: list[ExpenseDetailRead] = Field(default_factory=list)
    attachments: list[AttachmentRead] = Field(default_factory=list)
    validation_summary: "ReimbursementValidationSummary"
    payments: list[PaymentRead] = Field(default_factory=list)
    audit_events: list[AuditLogRead] = Field(default_factory=list)
    available_actions: list[str] = Field(default_factory=list)


class ReimbursementRequestTransition(BaseModel):
    target_status: ReimbursementRequestStatus
    actor_user_id: UUID
    note: str | None = Field(default=None, max_length=1000)


class AuthenticatedReimbursementRequestTransition(BaseModel):
    target_status: ReimbursementRequestStatus
    note: str | None = Field(default=None, max_length=1000)


class SapPolicyPrepare(BaseModel):
    actor_user_id: UUID
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class AuthenticatedSapPolicyPrepare(BaseModel):
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class SapPolicyRead(BaseModel):
    request_id: UUID
    status: str
    reference: str
    generated_at: datetime
    generated_by_user_id: UUID
    payload: dict


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
    removed_expense_ids: list[UUID]
    rejected_expense_ids: list[UUID]
    missing_authorization_expense_ids: list[UUID]
    missing_receipt_expense_ids: list[UUID]
    missing_cfdi_expense_ids: list[UUID]
    out_of_period_expense_ids: list[UUID]
    duplicate_cfdi_uuids: list[str]
    invalid_cfdi_expense_ids: list[UUID]
    ready_for_submission: bool
    ready_for_authorization_approval: bool
    ready_for_accounting_approval: bool
    is_balanced: bool
    issues: list[ReimbursementValidationIssue]


class AutomatedReviewStep(BaseModel):
    code: str
    label: str
    responsibility: str = "automatic"
    status: str
    message: str
    blocking: bool = False
    issue_codes: list[str] = Field(default_factory=list)
    expense_ids: list[UUID] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)


class AutomatedReviewRead(BaseModel):
    request_id: UUID
    overall_status: str
    automatic_steps: list[AutomatedReviewStep]
    human_steps: list[AutomatedReviewStep]
    alerts: list[ReimbursementValidationIssue]
    summary: ReimbursementValidationSummary
