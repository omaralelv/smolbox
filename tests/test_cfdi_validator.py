from decimal import Decimal
from types import SimpleNamespace

from app.schemas.cfdi import CfdiParseResult
from app.services.cfdi_validator import validate_cfdi_for_expense


def test_validate_cfdi_accepts_matching_expense() -> None:
    parsed = CfdiParseResult(
        uuid="11111111-2222-3333-4444-555555555555",
        total=Decimal("123.45"),
        currency="MXN",
        receiver_rfc="BBB010101BBB",
    )
    expense = SimpleNamespace(amount=Decimal("123.45"), currency="MXN")

    result = validate_cfdi_for_expense(parsed, expense, expected_receiver_rfc="BBB010101BBB")

    assert result.is_valid is True
    assert result.issues == []


def test_validate_cfdi_reports_mismatches() -> None:
    parsed = CfdiParseResult(
        uuid=None,
        total=Decimal("100.00"),
        currency="USD",
        receiver_rfc="AAA010101AAA",
    )
    expense = SimpleNamespace(amount=Decimal("123.45"), currency="MXN")

    result = validate_cfdi_for_expense(parsed, expense, expected_receiver_rfc="BBB010101BBB")

    assert result.is_valid is False
    assert {issue.code for issue in result.issues} == {
        "missing_uuid",
        "total_mismatch",
        "currency_mismatch",
        "receiver_rfc_mismatch",
    }
