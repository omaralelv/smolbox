from decimal import Decimal
from typing import Protocol
from uuid import UUID

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
    elif normalize_cfdi_uuid(parsed.uuid) is None:
        issues.append(
            CfdiValidationIssue(
                code="invalid_uuid",
                message="CFDI UUID does not have a valid UUID format.",
            )
        )
    else:
        parsed.uuid = normalize_cfdi_uuid(parsed.uuid)

    if not parsed.issuer_rfc:
        issues.append(
            CfdiValidationIssue(
                code="missing_issuer_rfc",
                message="CFDI issuer RFC is required.",
            )
        )

    if not parsed.receiver_rfc:
        issues.append(
            CfdiValidationIssue(
                code="missing_receiver_rfc",
                message="CFDI receiver RFC is required.",
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

    if not parsed.currency:
        issues.append(
            CfdiValidationIssue(
                code="missing_currency",
                message="CFDI currency is required.",
            )
        )
    elif parsed.currency.upper() != expense.currency.upper():
        issues.append(
            CfdiValidationIssue(
                code="currency_mismatch",
                message="CFDI currency does not match the expense currency.",
            )
        )

    if (
        expected_receiver_rfc
        and parsed.receiver_rfc
        and parsed.receiver_rfc.upper() != expected_receiver_rfc.upper()
    ):
        issues.append(
            CfdiValidationIssue(
                code="receiver_rfc_mismatch",
                message="CFDI receiver RFC does not match the configured company RFC.",
            )
        )

    if parsed.issued_at is None:
        issues.append(
            CfdiValidationIssue(
                code="missing_issued_at",
                message="CFDI issue date is required.",
            )
        )
    else:
        period = getattr(expense, "period", None)
        if period is not None and not (
            period.starts_on <= parsed.issued_at.date() <= period.ends_on
        ):
            issues.append(
                CfdiValidationIssue(
                    code="issued_at_outside_period",
                    message="CFDI issue date is outside the reimbursement period.",
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


def normalize_cfdi_uuid(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(value.strip())).upper()
    except (AttributeError, ValueError):
        return None
