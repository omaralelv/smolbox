from sqlalchemy import String, cast, func, or_

from app.models.audit_log import AuditLog
from app.models.user import User, UserRole

OBSERVATION_ACTIONS = {
    "expense_observation_added",
    "expense_removed_from_request",
    "expense_review_updated",
    "expense_authorization_rejected",
    "expense_partitioned",
    "expense_partition_updated",
    "expense_partition_cancelled",
}

PUBLIC_OBSERVATION_ACTIONS = {
    "expense_removed_from_request",
    "expense_authorization_rejected",
}


def public_audit_event_condition():
    # Prefer the role recorded at the time of the event over later role changes.
    actor_role = func.coalesce(
        AuditLog.event_payload["actor_role"].as_string(), cast(User.role, String),
    )
    return or_(
        AuditLog.action.not_in(OBSERVATION_ACTIONS),
        AuditLog.action.in_(PUBLIC_OBSERVATION_ACTIONS),
        AuditLog.event_payload["is_initial_observation"].as_boolean().is_(True),
        actor_role.in_([UserRole.store.value, UserRole.authorizer.value]),
    )
