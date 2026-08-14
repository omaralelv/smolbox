from decimal import Decimal
from uuid import UUID

from app.models.reimbursement_request import ReimbursementRequest
from app.schemas.reimbursement_request import (
    AutomatedReviewRead,
    AutomatedReviewStep,
    ReimbursementValidationSummary,
)


def build_automated_review(
    request: ReimbursementRequest,
    summary: ReimbursementValidationSummary,
) -> AutomatedReviewRead:
    automatic_steps = [
        _receipt_step(summary),
        _cfdi_step(summary),
        _total_step(summary),
        _period_step(summary),
        _ocr_step(),
        _alerts_step(summary),
        _sap_policy_data_step(request, summary),
    ]
    human_steps = _human_steps(summary)
    blocking = any(step.blocking for step in automatic_steps)
    attention = any(step.status in {"attention", "not_configured"} for step in automatic_steps)
    overall_status = "blocked" if blocking else "attention" if attention else "passed"

    return AutomatedReviewRead(
        request_id=request.id,
        overall_status=overall_status,
        automatic_steps=automatic_steps,
        human_steps=human_steps,
        alerts=summary.issues,
        summary=summary,
    )


def _receipt_step(summary: ReimbursementValidationSummary) -> AutomatedReviewStep:
    missing = summary.missing_receipt_expense_ids
    if missing:
        return _step(
            "receipt_check",
            "Revisar comprobantes",
            "blocked",
            "Hay gastos sin comprobante.",
            blocking=True,
            issue_codes=["missing_receipts"],
            expense_ids=missing,
        )
    return _step("receipt_check", "Revisar comprobantes", "passed", "Todos los gastos activos tienen comprobante.")


def _cfdi_step(summary: ReimbursementValidationSummary) -> AutomatedReviewStep:
    blocking_issue_codes = []
    expense_ids: list[UUID] = []
    if summary.invalid_cfdi_expense_ids:
        blocking_issue_codes.append("invalid_cfdi")
        expense_ids.extend(summary.invalid_cfdi_expense_ids)
    if summary.duplicate_cfdi_uuids:
        blocking_issue_codes.append("duplicate_cfdi_uuid")

    if blocking_issue_codes:
        return _step(
            "cfdi_validation",
            "Validar CFDI",
            "blocked",
            "Hay CFDI invalidos o duplicados.",
            blocking=True,
            issue_codes=blocking_issue_codes,
            expense_ids=expense_ids,
            data={"duplicate_cfdi_uuids": summary.duplicate_cfdi_uuids},
        )
    if summary.missing_cfdi_expense_ids:
        return _step(
            "cfdi_validation",
            "Validar CFDI",
            "blocked",
            "Falta CFDI XML vigente en uno o mas gastos.",
            blocking=True,
            issue_codes=["missing_cfdi_xml"],
            expense_ids=summary.missing_cfdi_expense_ids,
        )
    return _step("cfdi_validation", "Validar CFDI", "passed", "Los CFDI activos estan presentes y vigentes.")


def _total_step(summary: ReimbursementValidationSummary) -> AutomatedReviewStep:
    if summary.difference is not None and summary.difference != Decimal("0.00"):
        return _step(
            "total_balance",
            "Detectar total descuadrado",
            "blocked",
            "El total reportado no coincide con la suma de gastos activos.",
            blocking=True,
            issue_codes=["reported_total_mismatch"],
            data={
                "reported_total": str(summary.reported_total),
                "calculated_total": str(summary.calculated_total),
                "difference": str(summary.difference),
            },
        )
    return _step(
        "total_balance",
        "Detectar total descuadrado",
        "passed",
        "El total reportado coincide con la suma activa.",
    )


def _period_step(summary: ReimbursementValidationSummary) -> AutomatedReviewStep:
    if summary.out_of_period_expense_ids:
        return _step(
            "period_check",
            "Detectar gastos fuera de periodo",
            "blocked",
            "Hay gastos fuera del periodo de reembolso.",
            blocking=True,
            issue_codes=["expense_outside_period"],
            expense_ids=summary.out_of_period_expense_ids,
        )
    return _step(
        "period_check",
        "Detectar gastos fuera de periodo",
        "passed",
        "Todos los gastos activos estan dentro del periodo.",
    )


def _ocr_step() -> AutomatedReviewStep:
    return _step(
        "ocr_extraction",
        "Ejecutar OCR",
        "not_configured",
        "OCR queda reservado para conectar el motor real; por ahora no bloquea el flujo.",
        data={"engine": "pending"},
    )


def _alerts_step(summary: ReimbursementValidationSummary) -> AutomatedReviewStep:
    if summary.issues:
        return _step(
            "alerts",
            "Generar alertas",
            "attention",
            "Se generaron alertas automaticas para revision.",
            issue_codes=[issue.code for issue in summary.issues],
            data={"alert_count": len(summary.issues)},
        )
    return _step("alerts", "Generar alertas", "passed", "No hay alertas automaticas.")


def _sap_policy_data_step(
    request: ReimbursementRequest,
    summary: ReimbursementValidationSummary,
) -> AutomatedReviewStep:
    data = {
        "request_id": str(request.id),
        "store_id": str(request.store_id),
        "period_id": str(request.period_id),
        "reported_total": str(summary.reported_total),
        "calculated_total": str(summary.calculated_total),
        "expense_count": summary.expense_count,
    }
    if summary.ready_for_accounting_approval:
        return _step(
            "sap_policy_data",
            "Preparar datos para poliza SAP",
            "ready",
            "Los datos base para la poliza SAP estan listos.",
            data=data,
        )
    return _step(
        "sap_policy_data",
        "Preparar datos para poliza SAP",
        "blocked",
        "Faltan validaciones automaticas antes de preparar la poliza SAP.",
        blocking=True,
        issue_codes=[issue.code for issue in summary.issues],
        data=data,
    )


def _human_steps(summary: ReimbursementValidationSummary) -> list[AutomatedReviewStep]:
    steps = []
    if summary.missing_authorization_expense_ids:
        steps.append(
            _step(
                "authorize_or_reject_product",
                "Autorizar o rechazar producto",
                "pending",
                "Autorizacion debe decidir sobre gastos marcados para autorizacion.",
                responsibility="human",
                blocking=True,
                issue_codes=["missing_authorization"],
                expense_ids=summary.missing_authorization_expense_ids,
            )
        )

    steps.extend(
        [
            _step(
                "manager_approval",
                "Aprobar gerente",
                "pending",
                "Gerente de contabilidad debe aprobar despues de contabilidad.",
                responsibility="human",
            ),
            _step(
                "direction_approval",
                "Aprobar direccion",
                "pending",
                "Direccion debe aprobar antes de liberar pago.",
                responsibility="human",
            ),
            _step(
                "payment_confirmation",
                "Registrar pago",
                "pending",
                "Tesoreria debe registrar el pago formal.",
                responsibility="human",
            ),
        ]
    )
    return steps


def _step(
    code: str,
    label: str,
    status: str,
    message: str,
    *,
    responsibility: str = "automatic",
    blocking: bool = False,
    issue_codes: list[str] | None = None,
    expense_ids: list[UUID] | None = None,
    data: dict | None = None,
) -> AutomatedReviewStep:
    return AutomatedReviewStep(
        code=code,
        label=label,
        responsibility=responsibility,
        status=status,
        message=message,
        blocking=blocking,
        issue_codes=issue_codes or [],
        expense_ids=expense_ids or [],
        data=data or {},
    )
