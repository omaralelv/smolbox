from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole
from app.schemas.reimbursement_request import ReimbursementValidationSummary
from app.services.workflow import WorkflowTransitionError, transition_reimbursement_request


def _summary(
    *,
    ready_for_submission: bool = True,
    ready_for_accounting_approval: bool = True,
) -> ReimbursementValidationSummary:
    return ReimbursementValidationSummary(
        request_id=uuid4(),
        reported_total=Decimal("100.00"),
        calculated_total=Decimal("100.00"),
        difference=Decimal("0.00"),
        expense_count=1,
        category_totals=[],
        missing_receipt_expense_ids=[],
        missing_cfdi_expense_ids=[],
        out_of_period_expense_ids=[],
        duplicate_cfdi_uuids=[],
        invalid_cfdi_expense_ids=[],
        ready_for_submission=ready_for_submission,
        ready_for_accounting_approval=ready_for_accounting_approval,
        is_balanced=True,
        issues=[],
    )


def test_store_user_can_submit_ready_request() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.draft)
    actor = User(
        email="tienda@example.com",
        full_name="Tienda Demo",
        role=UserRole.store,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.submitted,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.draft
    assert to_status == ReimbursementRequestStatus.submitted
    assert request.status == ReimbursementRequestStatus.submitted
    assert request.submitted_at is not None


def test_accounting_approval_requires_accounting_ready_request() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.under_accounting_review)
    actor = User(
        email="contador@example.com",
        full_name="Contador Demo",
        role=UserRole.accountant,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError):
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.accounting_approved,
            summary=_summary(ready_for_accounting_approval=False),
        )
