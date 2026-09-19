from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.authorization_area import UserAuthorizationArea
from app.models.store import Store, StoreUserAssignment
from app.models.user import User, UserRole
from app.services.authorization_areas import get_or_create_authorization_area
from app.services.security import hash_password
from app.services.store_catalog import cargar_base_tiendas

SUPERVISOR_AREA = "supervisores"
REQUIRED_COLUMNS = (
    "PLAZA",
    "CORREO DE TIENDA",
    "SUPERVISOR",
    "CORREO DE SUPERVISOR",
    "RESPONSABLE",
    "CORREO DE RESPONSABLE",
)


@dataclass
class ImportResult:
    created_users: list[str] = field(default_factory=list)
    skipped_users: list[str] = field(default_factory=list)
    created_stores: list[str] = field(default_factory=list)
    skipped_stores: list[str] = field(default_factory=list)
    created_assignments: int = 0
    skipped_assignments: int = 0
    invalid_rows: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def import_initial_catalog(
    db: Session,
    path: str | Path,
    *,
    password: str | None = None,
) -> ImportResult:
    """Import new users, stores and assignments without changing existing rows.

    The caller owns the transaction. Any exception raised after this function returns
    can be rolled back by the caller as a single import operation.
    """
    catalog = cargar_base_tiendas(str(path))
    if not catalog:
        raise ValueError(f"Excel vacío o no legible: {path}")

    _validate_columns(catalog)
    result = ImportResult()
    area = get_or_create_authorization_area(db, SUPERVISOR_AREA)
    known_users = {
        user.email: user for user in db.scalars(select(User))
    }
    pending_users: dict[str, tuple[str, UserRole]] = {}

    for row_number, (code, row) in enumerate(catalog.items(), start=2):
        row_result = _import_row(
            db,
            row,
            code=code,
            row_number=row_number,
            area_id=area.id,
            known_users=known_users,
            pending_users=pending_users,
            result=result,
            password=password,
        )
        if row_result is None:
            continue

    db.flush()
    return result


def _import_row(
    db: Session,
    row: dict[str, object],
    *,
    code: str,
    row_number: int,
    area_id,
    known_users: dict[str, User],
    pending_users: dict[str, tuple[str, UserRole]],
    result: ImportResult,
    password: str | None,
) -> bool | None:
    code = _clean(code)
    if not code:
        result.invalid_rows.append(f"Fila {row_number}: TDA vacío")
        return None

    store_name = _clean(row.get("PLAZA"))
    store_email = _clean_email(row.get("CORREO DE TIENDA"))
    supervisor_name = _clean(row.get("SUPERVISOR"))
    supervisor_email = _clean_email(row.get("CORREO DE SUPERVISOR"))
    accountant_name = _clean(row.get("RESPONSABLE"))
    accountant_email = _clean_email(row.get("CORREO DE RESPONSABLE"))

    if not store_name or not store_email:
        result.invalid_rows.append(f"Fila {row_number} ({code}): tienda sin nombre o correo")
        return None

    identities = (
        ("tienda", store_email, store_name, UserRole.store),
        ("supervisor", supervisor_email, supervisor_name, UserRole.authorizer),
        ("contador", accountant_email, accountant_name, UserRole.accountant),
    )
    for label, email, name, role in identities:
        if not email or not name:
            result.invalid_rows.append(f"Fila {row_number} ({code}): {label} incompleto")
            return None
        prior = pending_users.get(email)
        if prior is not None and prior[1] != role:
            result.conflicts.append(
                f"Fila {row_number} ({code}): {email} aparece con roles incompatibles"
            )
            return None
        existing = known_users.get(email)
        if existing is not None and existing.role != role:
            result.conflicts.append(
                f"Fila {row_number} ({code}): {email} ya existe con rol {existing.role.value}"
            )
            return None

    users: dict[UserRole, User | None] = {}
    for _, email, name, role in identities:
        pending = pending_users.get(email)
        if pending is not None:
            users[role] = known_users[email]
            continue

        user = known_users.get(email)
        if user is not None:
            result.skipped_users.append(email)
            users[role] = None
            continue

        user = User(
            email=email,
            full_name=name,
            role=role,
            is_active=False,
            password_hash=hash_password(password) if password else None,
        )
        db.add(user)
        db.flush()
        known_users[email] = user
        pending_users[email] = (name, role)
        result.created_users.append(email)
        users[role] = user

        if role == UserRole.authorizer:
            db.add(
                UserAuthorizationArea(
                    user_id=user.id,
                    authorization_area_id=area_id,
                    is_active=False,
                )
            )

    store = db.scalar(select(Store).where(Store.code == code))
    if store is not None:
        result.skipped_stores.append(code)
        return True

    store = Store(
        code=code,
        name=store_name,
        contact_email=store_email,
        assigned_accountant=accountant_name,
        manager_name=_clean(row.get("NOMBRE_GERENTE")) or None,
        bank_account=_clean(row.get("CUENTA")) or None,
        state_region=store_name,
    )
    db.add(store)
    db.flush()
    result.created_stores.append(code)

    for role, user in users.items():
        if user is None:
            continue
        db.add(
            StoreUserAssignment(
                store_id=store.id,
                user_id=user.id,
                role=role,
                is_active=False,
            )
        )
        result.created_assignments += 1
    return True


def _validate_columns(catalog: dict[str, dict[str, object]]) -> None:
    first_row = next(iter(catalog.values()))
    missing = [column for column in REQUIRED_COLUMNS if column not in first_row]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en el Excel: {', '.join(missing)}")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_email(value: object) -> str:
    return _clean(value).lower()
