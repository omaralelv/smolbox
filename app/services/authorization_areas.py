from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorization_area import AuthorizationArea, UserAuthorizationArea
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.models.user import User, UserRole

DEFAULT_AUTHORIZATION_AREA_NAMES = (
    "Auditoría Interna",
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
    if user.role != UserRole.authorizer:
        return set()

    return set(
        db.scalars(
            select(UserAuthorizationArea.authorization_area_id)
            .join(AuthorizationArea)
            .where(
                UserAuthorizationArea.user_id == user.id,
                UserAuthorizationArea.is_active.is_(True),
                AuthorizationArea.is_active.is_(True),
            )
        )
    )


def user_can_authorize_expense_area(db: Session, user: User, expense: Expense) -> bool:
    if user.role == UserRole.admin:
        return True
    if user.role != UserRole.authorizer:
        return False

    active_area_ids = active_authorization_area_ids_for_user(db, user)
    if not active_area_ids:
        return True

    return expense.authorization_area_id in active_area_ids


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

    active_area_ids = active_authorization_area_ids_for_user(db, user)
    if not active_area_ids:
        return True

    return any(
        expense.id in pending_expense_ids
        and expense.authorization_area_id in active_area_ids
        for expense in request.expenses
    )


def request_has_authorization_area_for_user(
    request: ReimbursementRequest,
    user: User,
    db: Session,
) -> bool:
    if user.role != UserRole.authorizer:
        return True

    active_area_ids = active_authorization_area_ids_for_user(db, user)
    if not active_area_ids:
        return True

    return any(
        expense.requires_authorization
        and expense.authorization_area_id in active_area_ids
        for expense in request.expenses
    )


def expense_is_visible_to_authorizer(db: Session, user: User, expense: Expense) -> bool:
    if user.role != UserRole.authorizer:
        return True
    if not expense.requires_authorization:
        return True

    active_area_ids = active_authorization_area_ids_for_user(db, user)
    if not active_area_ids:
        return True

    return expense.authorization_area_id in active_area_ids
