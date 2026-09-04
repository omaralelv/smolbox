from datetime import UTC, datetime
from uuid import UUID

from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User, UserRole


class SapPolicyPreparationError(ValueError):
    pass


def prepare_sap_policy_placeholder(
    request: ReimbursementRequest,
    *,
    actor: User,
    reference: str | None = None,
) -> dict:
    if not actor.is_active:
        raise SapPolicyPreparationError("Actor user is inactive")
    if actor.role not in {UserRole.accountant, UserRole.admin}:
        raise SapPolicyPreparationError("Only accounting or admin users can prepare SAP policy")
    if request.status != ReimbursementRequestStatus.accounting_reviewed:
        raise SapPolicyPreparationError(
            "SAP policy can be prepared after accounting review is completed"
        )

    generated_at = datetime.now(UTC)
    policy_reference = reference or _default_policy_reference(request.id)
    payload = {
        "status": "placeholder",
        "integration": "sap_policy_generator",
        "message": "Pending external SAP policy generator code.",
        "request_id": str(request.id),
        "store_id": str(request.store_id),
        "period_id": str(request.period_id),
        "generated_at": generated_at.isoformat(),
    }
    request.sap_policy_generated_at = generated_at
    request.sap_policy_generated_by_user_id = actor.id
    request.sap_policy_reference = policy_reference
    request.sap_policy_payload = payload
    return payload


def _default_policy_reference(request_id: UUID) -> str:
    return f"SAP-POLICY-PENDING-{str(request_id)[:8].upper()}"
