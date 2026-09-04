from datetime import UTC, datetime
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
        removed_expense_ids=[],
        rejected_expense_ids=[],
        missing_authorization_expense_ids=[],
        missing_receipt_expense_ids=[],
        missing_cfdi_expense_ids=[],
        out_of_period_expense_ids=[],
        duplicate_cfdi_uuids=[],
        invalid_cfdi_expense_ids=[],
        ready_for_submission=ready_for_submission,
        ready_for_authorization_approval=True,
        ready_for_accounting_approval=ready_for_accounting_approval,
        is_balanced=True,
        issues=[],
    )


def _no_payable_summary() -> ReimbursementValidationSummary:
    summary = _summary(ready_for_submission=False, ready_for_accounting_approval=False)
    summary.reported_total = Decimal("0.00")
    summary.calculated_total = Decimal("0.00")
    summary.difference = Decimal("0.00")
    summary.expense_count = 0
    summary.rejected_expense_ids = [uuid4()]
    summary.ready_for_authorization_approval = False
    return summary


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


def test_store_user_cannot_submit_without_cfdi() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.draft)
    actor = User(
        email="tienda.sin.evidencia@example.com",
        full_name="Tienda Sin Evidencia",
        role=UserRole.store,
        is_active=True,
    )
    summary = _summary(ready_for_submission=False)
    summary.missing_receipt_expense_ids = [uuid4()]
    summary.missing_cfdi_expense_ids = [uuid4()]

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.submitted,
            summary=summary,
        )

    assert "valid CFDI evidence" in str(exc_info.value)
    assert request.status == ReimbursementRequestStatus.draft


def test_store_user_can_submit_without_receipt_when_cfdi_is_valid() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.draft)
    actor = User(
        email="tienda.sin.vale@example.com",
        full_name="Tienda Sin Vale",
        role=UserRole.store,
        is_active=True,
    )
    summary = _summary()
    summary.missing_receipt_expense_ids = [uuid4()]

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.submitted,
        summary=summary,
    )

    assert from_status == ReimbursementRequestStatus.draft
    assert to_status == ReimbursementRequestStatus.submitted
    assert request.status == ReimbursementRequestStatus.submitted


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
            target_status=ReimbursementRequestStatus.accounting_reviewed,
            summary=_summary(ready_for_accounting_approval=False),
        )


def test_authorization_requires_authorized_expenses() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.authorization_review)
    actor = User(
        email="autorizador@example.com",
        full_name="Autorizador Demo",
        role=UserRole.authorizer,
        is_active=True,
    )

    summary = _summary()
    summary.ready_for_authorization_approval = False
    summary.missing_authorization_expense_ids = [uuid4()]

    with pytest.raises(WorkflowTransitionError):
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.authorized,
            summary=summary,
        )


def test_authorization_review_is_skipped_when_no_expenses_need_authorization() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.submitted)
    actor = User(
        email="autorizador.sin.pendientes@example.com",
        full_name="Autorizador Sin Pendientes",
        role=UserRole.authorizer,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.authorization_review,
            summary=_summary(),
        )

    assert "does not have expenses pending authorization" in str(exc_info.value)


def test_accountant_can_take_submitted_request_without_authorization_pending() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.submitted)
    actor = User(
        email="contador.directo@example.com",
        full_name="Contador Directo",
        role=UserRole.accountant,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.under_accounting_review,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.submitted
    assert to_status == ReimbursementRequestStatus.under_accounting_review
    assert request.status == ReimbursementRequestStatus.under_accounting_review


def test_accountant_cannot_take_submitted_request_with_authorization_pending() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.submitted)
    actor = User(
        email="contador.bloqueado@example.com",
        full_name="Contador Bloqueado",
        role=UserRole.accountant,
        is_active=True,
    )
    summary = _summary()
    summary.ready_for_authorization_approval = False
    summary.missing_authorization_expense_ids = [uuid4()]

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.under_accounting_review,
            summary=summary,
        )

    assert "needs authorization review" in str(exc_info.value)


def test_authorizer_cannot_return_request_to_store_for_correction() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.authorization_review)
    actor = User(
        email="autorizador.correccion@example.com",
        full_name="Autorizador Correccion",
        role=UserRole.authorizer,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.correction_required,
            summary=_summary(),
        )

    assert "Cannot move request" in str(exc_info.value)


def test_accountant_cannot_return_request_to_store_for_correction() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.under_accounting_review)
    actor = User(
        email="contador.correccion@example.com",
        full_name="Contador Correccion",
        role=UserRole.accountant,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.correction_required,
            summary=_summary(),
        )

    assert "Cannot move request" in str(exc_info.value)


def test_manager_can_return_request_to_accounting_for_rework() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.accounting_manager_review)
    actor = User(
        email="gerente.retrabajo@example.com",
        full_name="Gerente Retrabajo",
        role=UserRole.accounting_manager,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.under_accounting_review,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.accounting_manager_review
    assert to_status == ReimbursementRequestStatus.under_accounting_review
    assert request.status == ReimbursementRequestStatus.under_accounting_review


def test_accountant_cannot_pull_later_review_back_to_accounting() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.accounting_manager_review)
    actor = User(
        email="contador.retrabajo@example.com",
        full_name="Contador Retrabajo",
        role=UserRole.accountant,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.under_accounting_review,
            summary=_summary(),
        )

    assert "cannot return request" in str(exc_info.value)


def test_treasury_returns_request_to_accounting_manager_for_rework() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.treasury_review)
    actor = User(
        email="tesoreria.retrabajo@example.com",
        full_name="Tesoreria Retrabajo",
        role=UserRole.treasury,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.accounting_manager_review,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.treasury_review
    assert to_status == ReimbursementRequestStatus.accounting_manager_review
    assert request.status == ReimbursementRequestStatus.accounting_manager_review


def test_treasury_can_approve_payment_from_treasury_review() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.treasury_review)
    actor = User(
        email="tesoreria.aprueba@example.com",
        full_name="Tesoreria Aprueba",
        role=UserRole.treasury,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.direction_approved,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.treasury_review
    assert to_status == ReimbursementRequestStatus.direction_approved
    assert request.status == ReimbursementRequestStatus.direction_approved
    assert request.direction_approved_at is not None


def test_accounting_manager_can_prepare_request_for_payment_confirmation() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.direction_approved)
    actor = User(
        email="gerencia.confirma@example.com",
        full_name="Gerencia Confirma",
        role=UserRole.accounting_manager,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.approved_for_payment,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.direction_approved
    assert to_status == ReimbursementRequestStatus.approved_for_payment
    assert request.status == ReimbursementRequestStatus.approved_for_payment
    assert request.approved_for_payment_at is not None


def test_director_returns_request_to_treasury_for_rework() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.direction_review)
    actor = User(
        email="direccion.retrabajo@example.com",
        full_name="Direccion Retrabajo",
        role=UserRole.director,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.treasury_review,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.direction_review
    assert to_status == ReimbursementRequestStatus.treasury_review
    assert request.status == ReimbursementRequestStatus.treasury_review


def test_treasury_cannot_return_request_directly_to_accounting() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.treasury_review)
    actor = User(
        email="tesoreria.salto@example.com",
        full_name="Tesoreria Salto",
        role=UserRole.treasury,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.under_accounting_review,
            summary=_summary(),
        )

    assert "Cannot move request from treasury_review to under_accounting_review" in str(
        exc_info.value
    )


def test_authorizer_can_reject_request_when_no_payable_expenses_remain() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.authorization_review)
    actor = User(
        email="autorizador.sin.monto@example.com",
        full_name="Autorizador Sin Monto",
        role=UserRole.authorizer,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.rejected,
        summary=_no_payable_summary(),
    )

    assert from_status == ReimbursementRequestStatus.authorization_review
    assert to_status == ReimbursementRequestStatus.rejected
    assert request.status == ReimbursementRequestStatus.rejected
    assert request.authorization_reviewed_at is not None


def test_authorizer_cannot_reject_request_when_payable_expenses_remain() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.authorization_review)
    actor = User(
        email="autorizador.con.monto@example.com",
        full_name="Autorizador Con Monto",
        role=UserRole.authorizer,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError) as exc_info:
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.rejected,
            summary=_summary(),
        )

    assert "no payable expenses remain" in str(exc_info.value)


def test_accountant_can_reject_request_when_no_payable_expenses_remain() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.under_accounting_review)
    actor = User(
        email="contador.sin.monto@example.com",
        full_name="Contador Sin Monto",
        role=UserRole.accountant,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.rejected,
        summary=_no_payable_summary(),
    )

    assert from_status == ReimbursementRequestStatus.under_accounting_review
    assert to_status == ReimbursementRequestStatus.rejected
    assert request.status == ReimbursementRequestStatus.rejected
    assert request.accounting_reviewed_at is not None


def test_manager_review_requires_sap_policy_placeholder() -> None:
    request = ReimbursementRequest(status=ReimbursementRequestStatus.accounting_reviewed)
    actor = User(
        email="gerente@example.com",
        full_name="Gerente Demo",
        role=UserRole.accounting_manager,
        is_active=True,
    )

    with pytest.raises(WorkflowTransitionError):
        transition_reimbursement_request(
            request,
            actor=actor,
            target_status=ReimbursementRequestStatus.accounting_manager_review,
            summary=_summary(),
        )


def test_accountant_can_send_prepared_sap_policy_to_manager_review() -> None:
    request = ReimbursementRequest(
        status=ReimbursementRequestStatus.accounting_reviewed,
        sap_policy_generated_at=datetime.now(UTC),
    )
    actor = User(
        email="contador.preparado@example.com",
        full_name="Contador Preparado",
        role=UserRole.accountant,
        is_active=True,
    )

    from_status, to_status = transition_reimbursement_request(
        request,
        actor=actor,
        target_status=ReimbursementRequestStatus.accounting_manager_review,
        summary=_summary(),
    )

    assert from_status == ReimbursementRequestStatus.accounting_reviewed
    assert to_status == ReimbursementRequestStatus.accounting_manager_review
