from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.models.attachment import AttachmentType
from app.services.reimbursement_validation import summarize_reimbursement_request


def _expense(
    amount: str,
    category: str,
    attachment_types: list[AttachmentType],
    *,
    requires_authorization: bool = False,
    authorized: bool = False,
    removed: bool = False,
    rejected: bool = False,
):
    has_valid_cfdi = AttachmentType.cfdi_xml in attachment_types
    return SimpleNamespace(
        id=uuid4(),
        amount=Decimal(amount),
        category=category,
        requires_authorization=requires_authorization,
        authorized_at=object() if authorized else None,
        removed_at=object() if removed else None,
        status="removed" if removed else "rejected" if rejected else "draft",
        attachments=[SimpleNamespace(attachment_type=kind) for kind in attachment_types],
        cfdi_validations=[
            SimpleNamespace(is_current=True, is_valid=True)
        ]
        if has_valid_cfdi
        else [],
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
    assert summary.ready_for_authorization_approval is True
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
    assert summary.ready_for_authorization_approval is False
    assert summary.ready_for_accounting_approval is False
    assert {issue.code for issue in summary.issues} == {
        "reported_total_mismatch",
        "missing_receipts",
        "missing_cfdi_xml",
    }


def test_summarize_reimbursement_request_tracks_authorization_and_removed_expenses() -> None:
    pending_authorization = _expense(
        "100.00",
        "operacion",
        [AttachmentType.receipt, AttachmentType.cfdi_xml],
        requires_authorization=True,
    )
    removed = _expense(
        "50.00",
        "transporte",
        [AttachmentType.receipt, AttachmentType.cfdi_xml],
        removed=True,
    )
    request = SimpleNamespace(
        id=uuid4(),
        reported_total=Decimal("100.00"),
        expenses=[pending_authorization, removed],
    )

    summary = summarize_reimbursement_request(request)

    assert summary.calculated_total == Decimal("100.00")
    assert summary.expense_count == 1
    assert summary.removed_expense_ids == [removed.id]
    assert summary.missing_authorization_expense_ids == [pending_authorization.id]
    assert summary.ready_for_submission is True
    assert summary.ready_for_authorization_approval is False
    assert summary.ready_for_accounting_approval is False
    assert "missing_authorization" in {issue.code for issue in summary.issues}


def test_summarize_reimbursement_request_excludes_rejected_authorization_expenses() -> None:
    approved = _expense(
        "100.00",
        "papeleria",
        [AttachmentType.receipt, AttachmentType.cfdi_xml],
    )
    rejected = _expense(
        "50.00",
        "transporte",
        [AttachmentType.receipt, AttachmentType.cfdi_xml],
        requires_authorization=True,
        rejected=True,
    )
    request = SimpleNamespace(
        id=uuid4(),
        reported_total=Decimal("100.00"),
        expenses=[approved, rejected],
    )

    summary = summarize_reimbursement_request(request)

    assert summary.calculated_total == Decimal("100.00")
    assert summary.expense_count == 1
    assert summary.rejected_expense_ids == [rejected.id]
    assert summary.missing_authorization_expense_ids == []
    assert summary.ready_for_authorization_approval is True


def test_summarize_reimbursement_request_reports_no_payable_expenses() -> None:
    rejected = _expense(
        "50.00",
        "transporte",
        [AttachmentType.receipt, AttachmentType.cfdi_xml],
        requires_authorization=True,
        rejected=True,
    )
    request = SimpleNamespace(
        id=uuid4(),
        reported_total=Decimal("0.00"),
        expenses=[rejected],
    )

    summary = summarize_reimbursement_request(request)

    assert summary.calculated_total == Decimal("0.00")
    assert summary.difference == Decimal("0.00")
    assert summary.expense_count == 0
    assert summary.rejected_expense_ids == [rejected.id]
    assert summary.ready_for_submission is False
    assert summary.ready_for_authorization_approval is False
    assert summary.ready_for_accounting_approval is False
    assert summary.is_balanced is False
    assert "no_payable_expenses" in {issue.code for issue in summary.issues}
