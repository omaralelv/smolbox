from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.models.attachment import AttachmentType
from app.services.reimbursement_validation import summarize_reimbursement_request


def _expense(amount: str, category: str, attachment_types: list[AttachmentType]):
    return SimpleNamespace(
        id=uuid4(),
        amount=Decimal(amount),
        category=category,
        attachments=[SimpleNamespace(attachment_type=kind) for kind in attachment_types],
    )


def test_summarize_reimbursement_request_balances_reported_total() -> None:
    request = SimpleNamespace(
        id=uuid4(),
        reported_total=Decimal("150.00"),
        expenses=[
            _expense("100.00", "papeleria", [AttachmentType.receipt, AttachmentType.cfdi_xml]),
            _expense("50.00", "transporte", [AttachmentType.receipt, AttachmentType.cfdi_xml]),
        ],
    )

    summary = summarize_reimbursement_request(request)

    assert summary.is_balanced is True
    assert summary.calculated_total == Decimal("150.00")
    assert summary.difference == Decimal("0.00")
    assert summary.ready_for_submission is True
    assert summary.ready_for_accounting_approval is True
    assert summary.issues == []


def test_summarize_reimbursement_request_reports_missing_evidence() -> None:
    missing_evidence_expense = _expense("100.00", "papeleria", [])
    request = SimpleNamespace(
        id=uuid4(),
        reported_total=Decimal("150.00"),
        expenses=[missing_evidence_expense],
    )

    summary = summarize_reimbursement_request(request)

    assert summary.is_balanced is False
    assert summary.calculated_total == Decimal("100.00")
    assert summary.difference == Decimal("-50.00")
    assert summary.missing_receipt_expense_ids == [missing_evidence_expense.id]
    assert summary.missing_cfdi_expense_ids == [missing_evidence_expense.id]
    assert summary.ready_for_submission is False
    assert summary.ready_for_accounting_approval is False
    assert {issue.code for issue in summary.issues} == {
        "reported_total_mismatch",
        "missing_receipts",
        "missing_cfdi_xml",
    }
