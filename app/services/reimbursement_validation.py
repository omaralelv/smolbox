from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.models.attachment import AttachmentType
from app.schemas.reimbursement_request import (
    CategoryTotal,
    ReimbursementValidationIssue,
    ReimbursementValidationSummary,
)


class AttachmentLike(Protocol):
    attachment_type: AttachmentType | str


class CfdiValidationLike(Protocol):
    is_current: bool
    is_valid: bool


class ExpenseLike(Protocol):
    id: UUID
    amount: Decimal
    category: str | None
    attachments: list[AttachmentLike]
    cfdi_validations: list[CfdiValidationLike]


class ReimbursementRequestLike(Protocol):
    id: UUID
    reported_total: Decimal | None
    expenses: list[ExpenseLike]


def summarize_reimbursement_request(
    request: ReimbursementRequestLike,
) -> ReimbursementValidationSummary:
    category_totals: defaultdict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    category_counts: defaultdict[str, int] = defaultdict(int)
    missing_receipt_expense_ids: list[UUID] = []
    missing_cfdi_expense_ids: list[UUID] = []
    out_of_period_expense_ids: list[UUID] = []
    duplicate_cfdi_uuids: list[str] = []
    invalid_cfdi_expense_ids: list[UUID] = []
    seen_cfdi_uuids: dict[str, UUID] = {}

    calculated_total = Decimal("0.00")
    period = getattr(request, "period", None)
    period_starts_on = getattr(period, "starts_on", None)
    period_ends_on = getattr(period, "ends_on", None)

    for expense in request.expenses:
        amount = _money(expense.amount)
        calculated_total += amount
        category = expense.category or "uncategorized"
        category_totals[category] += amount
        category_counts[category] += 1

        if not _has_attachment_type(expense.attachments, AttachmentType.receipt):
            missing_receipt_expense_ids.append(expense.id)
        if not _has_attachment_type(expense.attachments, AttachmentType.cfdi_xml):
            missing_cfdi_expense_ids.append(expense.id)

        spent_on = getattr(expense, "spent_on", None)
        if _is_outside_period(spent_on, period_starts_on, period_ends_on):
            out_of_period_expense_ids.append(expense.id)

        cfdi_uuid = getattr(expense, "cfdi_uuid", None)
        if cfdi_uuid:
            normalized_uuid = str(cfdi_uuid).upper()
            if normalized_uuid in seen_cfdi_uuids:
                duplicate_cfdi_uuids.append(normalized_uuid)
            else:
                seen_cfdi_uuids[normalized_uuid] = expense.id

        if _has_invalid_current_cfdi_validation(getattr(expense, "cfdi_validations", [])):
            invalid_cfdi_expense_ids.append(expense.id)

    reported_total = _money(request.reported_total) if request.reported_total is not None else None
    difference = None if reported_total is None else _money(calculated_total - reported_total)

    issues: list[ReimbursementValidationIssue] = []
    if reported_total is None:
        issues.append(
            ReimbursementValidationIssue(
                code="missing_reported_total",
                message="The cash box request does not include the total reported by the store.",
            )
        )
    elif difference != Decimal("0.00"):
        issues.append(
            ReimbursementValidationIssue(
                code="reported_total_mismatch",
                message="The sum of expenses does not match the total reported by the store.",
            )
        )

    if missing_receipt_expense_ids:
        issues.append(
            ReimbursementValidationIssue(
                code="missing_receipts",
                message="One or more expenses do not have a receipt attachment.",
            )
        )

    if missing_cfdi_expense_ids:
        issues.append(
            ReimbursementValidationIssue(
                code="missing_cfdi_xml",
                message="One or more expenses do not have a CFDI XML attachment.",
                severity="warning",
            )
        )

    if out_of_period_expense_ids:
        issues.append(
            ReimbursementValidationIssue(
                code="expense_outside_period",
                message="One or more expenses are outside the reimbursement period.",
            )
        )

    if duplicate_cfdi_uuids:
        issues.append(
            ReimbursementValidationIssue(
                code="duplicate_cfdi_uuid",
                message="One or more CFDI UUIDs are duplicated in the request.",
            )
        )

    if invalid_cfdi_expense_ids:
        issues.append(
            ReimbursementValidationIssue(
                code="invalid_cfdi",
                message="One or more expenses have a current CFDI validation error.",
            )
        )

    has_error = any(issue.severity == "error" for issue in issues)
    ready_for_submission = (
        reported_total is not None
        and len(request.expenses) > 0
        and not has_error
    )
    ready_for_accounting_approval = (
        ready_for_submission
        and not missing_cfdi_expense_ids
        and not invalid_cfdi_expense_ids
        and not duplicate_cfdi_uuids
        and not out_of_period_expense_ids
    )

    return ReimbursementValidationSummary(
        request_id=request.id,
        reported_total=reported_total,
        calculated_total=_money(calculated_total),
        difference=difference,
        expense_count=len(request.expenses),
        category_totals=[
            CategoryTotal(
                category=category,
                total=_money(total),
                expense_count=category_counts[category],
            )
            for category, total in sorted(category_totals.items())
        ],
        missing_receipt_expense_ids=missing_receipt_expense_ids,
        missing_cfdi_expense_ids=missing_cfdi_expense_ids,
        out_of_period_expense_ids=out_of_period_expense_ids,
        duplicate_cfdi_uuids=sorted(set(duplicate_cfdi_uuids)),
        invalid_cfdi_expense_ids=invalid_cfdi_expense_ids,
        ready_for_submission=ready_for_submission,
        ready_for_accounting_approval=ready_for_accounting_approval,
        is_balanced=not has_error,
        issues=issues,
    )


def _has_attachment_type(attachments: list[AttachmentLike], expected: AttachmentType) -> bool:
    for attachment in attachments:
        attachment_type = attachment.attachment_type
        value = (
            attachment_type.value
            if isinstance(attachment_type, AttachmentType)
            else attachment_type
        )
        if value == expected.value:
            return True
    return False


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _is_outside_period(
    spent_on: date | datetime | None,
    starts_on: date | None,
    ends_on: date | None,
) -> bool:
    if spent_on is None or starts_on is None or ends_on is None:
        return False
    spent_date = spent_on.date() if isinstance(spent_on, datetime) else spent_on
    return spent_date < starts_on or spent_date > ends_on


def _has_invalid_current_cfdi_validation(validations: list[CfdiValidationLike]) -> bool:
    for validation in validations:
        if validation.is_current and not validation.is_valid:
            return True
    return False
