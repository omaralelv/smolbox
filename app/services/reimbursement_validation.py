from collections import defaultdict
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


class ExpenseLike(Protocol):
    id: UUID
    amount: Decimal
    category: str | None
    attachments: list[AttachmentLike]


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

    calculated_total = Decimal("0.00")
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
        is_balanced=not any(issue.severity == "error" for issue in issues),
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
