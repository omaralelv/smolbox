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
from app.services.cfdi_validator import normalize_cfdi_uuid


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
    missing_authorization_expense_ids: list[UUID] = []
    removed_expense_ids: list[UUID] = []
    rejected_expense_ids: list[UUID] = []
    missing_cfdi_expense_ids: list[UUID] = []
    out_of_period_expense_ids: list[UUID] = []
    duplicate_cfdi_uuids: list[str] = []
    invalid_cfdi_expense_ids: list[UUID] = []
    seen_cfdi_uuids: dict[str, UUID] = {}

    calculated_total = Decimal("0.00")
    period = getattr(request, "period", None)
    period_starts_on = getattr(period, "starts_on", None)
    period_ends_on = getattr(period, "ends_on", None)

    active_expenses = []
    for expense in request.expenses:
        if _is_removed(expense):
            removed_expense_ids.append(expense.id)
            continue
        if _is_rejected(expense):
            rejected_expense_ids.append(expense.id)
            continue

        active_expenses.append(expense)
        amount = _money(expense.amount)
        calculated_total += amount
        category = expense.category or "uncategorized"
        category_totals[category] += amount
        category_counts[category] += 1

        if (
            not _has_attachment_type(expense.attachments, AttachmentType.receipt)
            and not _has_attachment_type(
                expense.attachments,
                AttachmentType.other,
            )
        ):
            missing_receipt_expense_ids.append(expense.id)

        if _requires_authorization(expense) and not getattr(expense, "authorized_at", None):
            missing_authorization_expense_ids.append(expense.id)

        cfdi_validations = getattr(expense, "cfdi_validations", [])
        if not _has_valid_invoice_evidence(expense, cfdi_validations):
            missing_cfdi_expense_ids.append(expense.id)

        spent_on = getattr(expense, "spent_on", None)
        if _is_outside_period(spent_on, period_starts_on, period_ends_on):
            out_of_period_expense_ids.append(expense.id)

        cfdi_uuid = getattr(expense, "cfdi_uuid", None) or _valid_ocr_cfdi_uuid(expense)
        if cfdi_uuid:
            normalized_uuid = str(cfdi_uuid).upper()
            if normalized_uuid in seen_cfdi_uuids:
                duplicate_cfdi_uuids.append(normalized_uuid)
            else:
                seen_cfdi_uuids[normalized_uuid] = expense.id

        if _has_invalid_current_cfdi_validation(cfdi_validations):
            invalid_cfdi_expense_ids.append(expense.id)

    reported_total = _money(request.reported_total) if request.reported_total is not None else None
    difference = None if reported_total is None else _money(calculated_total - reported_total)
    has_any_expenses = bool(request.expenses)
    has_no_payable_expenses = len(active_expenses) == 0

    issues: list[ReimbursementValidationIssue] = []
    if has_no_payable_expenses:
        message = (
            "All expenses were rejected or removed; the request has no payable amount."
            if has_any_expenses
            else "The cash box request does not include any expenses."
        )
        issues.append(
            ReimbursementValidationIssue(
                code="no_payable_expenses",
                message=message,
            )
        )

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
                severity="warning",
            )
        )

    if missing_authorization_expense_ids:
        issues.append(
            ReimbursementValidationIssue(
                code="missing_authorization",
                message="One or more expenses still require authorization.",
                severity="warning",
            )
        )

    if missing_cfdi_expense_ids:
        issues.append(
            ReimbursementValidationIssue(
                code="missing_cfdi_xml",
                message="One or more expenses do not have valid invoice, receipt, or voucher evidence.",
                severity="warning",
            )
        )

    if out_of_period_expense_ids:
        issues.append(
            ReimbursementValidationIssue(
                code="expense_outside_period",
                message=(
                    "One or more expenses are outside "
                    "the reimbursement period."
                ),
                severity="warning",
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
    has_required_store_evidence = (
        not missing_cfdi_expense_ids
        and not invalid_cfdi_expense_ids
    )
    ready_for_submission = (
        reported_total is not None
        and len(active_expenses) > 0
        and has_required_store_evidence
        and not has_error
    )
    ready_for_authorization_approval = (
        ready_for_submission and not missing_authorization_expense_ids
    )
    ready_for_accounting_approval = (
        ready_for_authorization_approval
        and not missing_cfdi_expense_ids
        and not invalid_cfdi_expense_ids
        and not duplicate_cfdi_uuids
    )

    return ReimbursementValidationSummary(
        request_id=request.id,
        reported_total=reported_total,
        calculated_total=_money(calculated_total),
        difference=difference,
        expense_count=len(active_expenses),
        category_totals=[
            CategoryTotal(
                category=category,
                total=_money(total),
                expense_count=category_counts[category],
            )
            for category, total in sorted(category_totals.items())
        ],
        removed_expense_ids=removed_expense_ids,
        rejected_expense_ids=rejected_expense_ids,
        missing_authorization_expense_ids=missing_authorization_expense_ids,
        missing_receipt_expense_ids=missing_receipt_expense_ids,
        missing_cfdi_expense_ids=missing_cfdi_expense_ids,
        out_of_period_expense_ids=out_of_period_expense_ids,
        duplicate_cfdi_uuids=sorted(set(duplicate_cfdi_uuids)),
        invalid_cfdi_expense_ids=invalid_cfdi_expense_ids,
        ready_for_submission=ready_for_submission,
        ready_for_authorization_approval=ready_for_authorization_approval,
        ready_for_accounting_approval=ready_for_accounting_approval,
        is_balanced=not has_error,
        issues=issues,
    )


def _has_attachment_type(attachments: list[AttachmentLike], expected: AttachmentType) -> bool:
    for attachment in attachments:
        if _attachment_type_value(attachment) == expected.value:
            return True
    return False


def _has_valid_invoice_evidence(
    expense: ExpenseLike,
    cfdi_validations: list[CfdiValidationLike],
) -> bool:
    if _has_attachment_type(expense.attachments, AttachmentType.cfdi_xml):
        return _has_current_cfdi_validation(cfdi_validations)
    if _valid_ocr_cfdi_uuid(expense) is not None:
        return True
    if normalize_cfdi_uuid(getattr(expense, "cfdi_uuid", None)):
        return False
    if _has_attachment_type(expense.attachments, AttachmentType.other):
        return True
    if _has_ocr_invoice_hint(expense):
        return False
    return _has_non_invoice_expense_evidence(expense)


def _has_non_invoice_expense_evidence(expense: ExpenseLike) -> bool:
    return _has_attachment_type(
        expense.attachments,
        AttachmentType.receipt,
    ) or _has_attachment_type(
        expense.attachments,
        AttachmentType.other,
    )


def _has_ocr_invoice_hint(expense: ExpenseLike) -> bool:
    for attachment in getattr(expense, "attachments", []):
        if _attachment_type_value(attachment) not in {
            AttachmentType.receipt.value,
            AttachmentType.other.value,
        }:
            continue
        extraction = getattr(attachment, "ocr_extraction", None)
        if extraction is None:
            continue
        if normalize_cfdi_uuid(getattr(extraction, "suggested_cfdi_uuid", None)):
            return True
    return False


def _valid_ocr_cfdi_uuid(expense: ExpenseLike) -> str | None:
    for attachment in getattr(expense, "attachments", []):
        if _attachment_type_value(attachment) not in {
            AttachmentType.receipt.value,
            AttachmentType.other.value,
        }:
            continue
        extraction = getattr(attachment, "ocr_extraction", None)
        if extraction is None:
            continue
        ocr_status = getattr(extraction, "status", None)
        if getattr(ocr_status, "value", ocr_status) != "succeeded":
            continue
        if not _ocr_total_matches_expense(expense, extraction):
            continue

        confirmed_uuid = normalize_cfdi_uuid(getattr(expense, "cfdi_uuid", None))
        suggested_uuid = normalize_cfdi_uuid(getattr(extraction, "suggested_cfdi_uuid", None))
        if confirmed_uuid or suggested_uuid:
            return confirmed_uuid or suggested_uuid
    return None


def _attachment_type_value(attachment: AttachmentLike) -> str:
    attachment_type = attachment.attachment_type
    return (
        attachment_type.value
        if isinstance(attachment_type, AttachmentType)
        else str(attachment_type)
    )


def _ocr_total_matches_expense(expense: ExpenseLike, extraction: object) -> bool:
    extracted_total = getattr(extraction, "extracted_total", None)
    if extracted_total is None:
        return False
    return _money(extracted_total) == _money(expense.amount)


def _ocr_date_matches_expense(expense: ExpenseLike, extraction: object) -> bool:
    extracted_date = getattr(extraction, "extracted_date", None)
    spent_on = getattr(expense, "spent_on", None)
    if extracted_date is None or spent_on is None:
        return False
    if isinstance(extracted_date, datetime):
        extracted_date = extracted_date.date()
    if isinstance(spent_on, datetime):
        spent_on = spent_on.date()
    return extracted_date == spent_on


def _ocr_matches_expense(expense: ExpenseLike, extraction: object) -> bool:
    return _ocr_total_matches_expense(expense, extraction) and _ocr_date_matches_expense(
        expense,
        extraction,
    )


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _is_removed(expense: ExpenseLike) -> bool:
    if getattr(expense, "removed_at", None) is not None:
        return True
    status = getattr(expense, "status", None)
    return getattr(status, "value", status) == "removed"


def _is_rejected(expense: ExpenseLike) -> bool:
    status = getattr(expense, "status", None)
    return getattr(status, "value", status) == "rejected"


def _requires_authorization(expense: ExpenseLike) -> bool:
    return bool(getattr(expense, "requires_authorization", False))


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


def _has_current_cfdi_validation(validations: list[CfdiValidationLike]) -> bool:
    for validation in validations:
        if validation.is_current:
            return True
    return False
