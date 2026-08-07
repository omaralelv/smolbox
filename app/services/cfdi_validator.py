from decimal import Decimal
from typing import Protocol

from app.schemas.cfdi import CfdiParseResult, CfdiValidationIssue, CfdiValidationResult


class ExpenseLike(Protocol):
    amount: Decimal
    currency: str


def validate_cfdi_for_expense(
    parsed: CfdiParseResult,
    expense: ExpenseLike,
    expected_receiver_rfc: str | None = None,
) -> CfdiValidationResult:
    issues: list[CfdiValidationIssue] = []

    if not parsed.uuid:
        issues.append(
            CfdiValidationIssue(
                code="missing_uuid",
                message="CFDI UUID is required for reimbursement evidence.",
            )
        )

    if parsed.total is None:
        issues.append(
            CfdiValidationIssue(
                code="missing_total",
                message="CFDI total is required to compare against the expense amount.",
            )
        )
    elif _money(parsed.total) != _money(expense.amount):
        issues.append(
            CfdiValidationIssue(
                code="total_mismatch",
                message="CFDI total does not match the expense amount.",
            )
        )

    if parsed.currency and parsed.currency.upper() != expense.currency.upper():
        issues.append(
            CfdiValidationIssue(
                code="currency_mismatch",
                message="CFDI currency does not match the expense currency.",
            )
        )

    if expected_receiver_rfc and parsed.receiver_rfc:
        if parsed.receiver_rfc.upper() != expected_receiver_rfc.upper():
            issues.append(
                CfdiValidationIssue(
                    code="receiver_rfc_mismatch",
                    message="CFDI receiver RFC does not match the configured company RFC.",
                )
            )

    for warning in parsed.warnings:
        issues.append(
            CfdiValidationIssue(
                code="parse_warning",
                message=warning,
                severity="warning",
            )
        )

    return CfdiValidationResult(
        is_valid=not any(i.severity == "error" for i in issues),
        parsed=parsed,
        issues=issues,
    )


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))
