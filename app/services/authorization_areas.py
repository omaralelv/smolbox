from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorization_area import AuthorizationArea, UserAuthorizationArea
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store import StoreUserAssignment
from app.models.user import User, UserRole

SUPERVISOR_AUTHORIZATION_AREA_NAME = "Supervisores"

DEFAULT_AUTHORIZATION_AREA_NAMES = (
    "Auditoría Interna",
    "Contabilidad",
    "Gestoría",
    "Insumos",
    "Mantenimiento",
    "Operaciones",
    "Pago de Luz",
    "Recursos Humanos",
    "Servicio de Agua",
    "Sistemas",
    "Supervisores",
    "Tráfico",
)


def normalize_authorization_area_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", without_accents.upper())
    return re.sub(r"\s+", " ", normalized).strip()


SUPERVISOR_AUTHORIZATION_AREA_NORMALIZED = normalize_authorization_area_name(
    SUPERVISOR_AUTHORIZATION_AREA_NAME
)


def clean_authorization_area_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def get_authorization_area_by_name(db: Session, name: str) -> AuthorizationArea | None:
    normalized_name = normalize_authorization_area_name(name)
    if not normalized_name:
        return None
    return db.scalar(
        select(AuthorizationArea).where(
            AuthorizationArea.normalized_name == normalized_name,
        )
    )


def get_or_create_authorization_area(
    db: Session,
    name: str,
    *,
    is_active: bool = True,
) -> AuthorizationArea:
    clean_name = clean_authorization_area_name(name)
    normalized_name = normalize_authorization_area_name(clean_name)
    if not normalized_name:
        raise ValueError("Authorization area name cannot be blank")

    area = get_authorization_area_by_name(db, clean_name)
    if area is not None:
        area.name = clean_name
        if is_active:
            area.is_active = True
        return area

    area = AuthorizationArea(
        name=clean_name,
        normalized_name=normalized_name,
        is_active=is_active,
    )
    db.add(area)
    db.flush()
    return area


def active_authorization_area_ids_for_user(db: Session, user: User) -> set[UUID]:
    return set(active_authorization_area_names_for_user(db, user))


def active_authorization_area_names_for_user(db: Session, user: User) -> dict[UUID, str]:
    if user.role != UserRole.authorizer:
        return {}

    rows = db.execute(
        select(AuthorizationArea.id, AuthorizationArea.normalized_name)
        .join(UserAuthorizationArea)
        .where(
            UserAuthorizationArea.user_id == user.id,
            UserAuthorizationArea.is_active.is_(True),
            AuthorizationArea.is_active.is_(True),
        )
    ).all()
    return {area_id: normalized_name for area_id, normalized_name in rows}


def authorizer_has_global_authorization_area(db: Session, user: User) -> bool:
    return any(
        normalized_name != SUPERVISOR_AUTHORIZATION_AREA_NORMALIZED
        for normalized_name in active_authorization_area_names_for_user(db, user).values()
    )


def user_can_authorize_expense_area(
    db: Session,
    user: User,
    expense: Expense,
    *,
    store_id: UUID | None = None,
) -> bool:
    if user.role == UserRole.admin:
        return True
    if user.role != UserRole.authorizer:
        return False

    active_areas = active_authorization_area_names_for_user(db, user)
    if not active_areas:
        return (
            store_id is not None
            and _user_has_authorizer_store_assignment(db, user, store_id)
            and _expense_is_store_supervisor_scoped(db, expense)
        )

    return _user_can_access_authorization_expense(
        db,
        user,
        expense,
        store_id=store_id,
        active_areas=active_areas,
    )


def request_has_authorization_visible_to_user(
    request: ReimbursementRequest,
    user: User,
    db: Session,
    *,
    pending_expense_ids: set[UUID],
) -> bool:
    if not pending_expense_ids:
        return False

    if user.role != UserRole.authorizer:
        return True

    active_areas = active_authorization_area_names_for_user(db, user)
    if not active_areas:
        return any(
            expense.id in pending_expense_ids
            and _user_has_authorizer_store_assignment(db, user, request.store_id)
            and _expense_is_store_supervisor_scoped(db, expense)
            for expense in request.expenses
        )

    return any(
        expense.id in pending_expense_ids
        and _user_can_access_authorization_expense(
            db,
            user,
            expense,
            store_id=request.store_id,
            active_areas=active_areas,
        )
        for expense in request.expenses
    )


def request_has_authorization_area_for_user(
    request: ReimbursementRequest,
    user: User,
    db: Session,
) -> bool:
    if user.role != UserRole.authorizer:
        return True

    active_areas = active_authorization_area_names_for_user(db, user)
    if not active_areas:
        return any(
            expense.requires_authorization
            and _user_has_authorizer_store_assignment(db, user, request.store_id)
            and _expense_is_store_supervisor_scoped(db, expense)
            for expense in request.expenses
        )

    return any(
        expense.requires_authorization
        and _user_can_access_authorization_expense(
            db,
            user,
            expense,
            store_id=request.store_id,
            active_areas=active_areas,
        )
        for expense in request.expenses
    )


def expense_is_visible_to_authorizer(
    db: Session,
    user: User,
    expense: Expense,
    *,
    store_id: UUID | None = None,
) -> bool:
    if user.role != UserRole.authorizer:
        return True
    if not expense.requires_authorization:
        return True

    active_areas = active_authorization_area_names_for_user(db, user)
    if not active_areas:
        return (
            store_id is not None
            and _user_has_authorizer_store_assignment(db, user, store_id)
            and _expense_is_store_supervisor_scoped(db, expense)
        )

    return _user_can_access_authorization_expense(
        db,
        user,
        expense,
        store_id=store_id,
        active_areas=active_areas,
    )


def _user_can_access_authorization_expense(
    db: Session,
    user: User,
    expense: Expense,
    *,
    store_id: UUID | None,
    active_areas: dict[UUID, str],
) -> bool:
    if expense.authorization_area_id is None:
        return (
            SUPERVISOR_AUTHORIZATION_AREA_NORMALIZED in active_areas.values()
            and store_id is not None
            and _user_has_authorizer_store_assignment(db, user, store_id)
        )

    normalized_area = active_areas.get(expense.authorization_area_id)
    if normalized_area is None:
        return False

    if normalized_area == SUPERVISOR_AUTHORIZATION_AREA_NORMALIZED:
        return (
            store_id is not None
            and _user_has_authorizer_store_assignment(db, user, store_id)
        )

    return True


def _expense_is_store_supervisor_scoped(db: Session, expense: Expense) -> bool:
    if expense.authorization_area_id is None:
        return True

    if expense.authorization_area is not None:
        return (
            expense.authorization_area.normalized_name
            == SUPERVISOR_AUTHORIZATION_AREA_NORMALIZED
        )

    normalized_name = db.scalar(
        select(AuthorizationArea.normalized_name).where(
            AuthorizationArea.id == expense.authorization_area_id,
        )
    )
    return normalized_name == SUPERVISOR_AUTHORIZATION_AREA_NORMALIZED


def _user_has_authorizer_store_assignment(db: Session, user: User, store_id: UUID) -> bool:
    return (
        db.scalar(
            select(StoreUserAssignment.id).where(
                StoreUserAssignment.store_id == store_id,
                StoreUserAssignment.user_id == user.id,
                StoreUserAssignment.role == UserRole.authorizer,
                StoreUserAssignment.is_active.is_(True),
            )
        )
        is not None
    )
