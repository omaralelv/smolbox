from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store import StoreUserAssignment
from app.models.user import User, UserRole


def user_has_store_assignment(
    db: Session,
    user: User,
    store_id: UUID,
    *,
    roles: set[UserRole] | None = None,
) -> bool:
    if user.role == UserRole.admin:
        return True
    statement = select(StoreUserAssignment.id).where(
        StoreUserAssignment.store_id == store_id,
        StoreUserAssignment.user_id == user.id,
        StoreUserAssignment.is_active.is_(True),
    )
    if roles is not None:
        statement = statement.where(StoreUserAssignment.role.in_(roles))
    return db.scalar(statement) is not None


def user_can_transition_store_request(db: Session, user: User, store_id: UUID) -> bool:
    review_roles = {
        UserRole.store,
        UserRole.authorizer,
        UserRole.accountant,
        UserRole.accounting_manager,
    }
    if user.role in {UserRole.treasury, UserRole.director, UserRole.admin}:
        return True
    return user_has_store_assignment(db, user, store_id, roles=review_roles)
