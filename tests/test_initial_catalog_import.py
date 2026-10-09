from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.models.authorization_area import AuthorizationArea, UserAuthorizationArea
from app.models.store import Store, StoreUserAssignment
from app.models.store_reimbursement_opening_cutoff import (
    StoreReimbursementOpeningCutoff,
)
from app.models.user import User, UserRole
from app.services import initial_catalog_import


def _catalog() -> dict[str, dict[str, str]]:
    return {
        "V001": {
            "TDA": "V001",
            "PLAZA": "SAN ANTONIO ABAD",
            "CORREO DE TIENDA": "t-001@example.com ",
            "SUPERVISOR": "Luisa Ramirez",
            "CORREO DE SUPERVISOR": "luisa@example.com",
            "RESPONSABLE": "Diana Teran",
            "CORREO DE RESPONSABLE": "diana@example.com",
            "NOMBRE_GERENTE": "Gerente Uno",
            "CUENTA": "123",
        },
        "V003": {
            "TDA": "V003",
            "PLAZA": "PORTALES",
            "CORREO DE TIENDA": "t-003@example.com",
            "SUPERVISOR": "Luisa Ramirez",
            "CORREO DE SUPERVISOR": "luisa@example.com",
            "RESPONSABLE": "Diana Teran",
            "CORREO DE RESPONSABLE": "diana@example.com",
            "NOMBRE_GERENTE": "Gerente Dos",
            "CUENTA": "456",
        },
    }


def test_import_deduplicates_users_and_allows_multiple_store_assignments(
    session_factory,
    monkeypatch,
) -> None:
    monkeypatch.setattr(initial_catalog_import, "cargar_base_tiendas", lambda _: _catalog())
    with session_factory() as db:
        result = initial_catalog_import.import_initial_catalog(db, "catalog.xlsx")
        db.commit()

        assert len(result.created_users) == 4
        assert result.created_stores == ["V001", "V003"]
        assert result.created_assignments == 6
        assert db.scalar(select(func.count()).select_from(User)) == 4
        assert db.scalar(select(func.count()).select_from(StoreUserAssignment)) == 6
        cutoffs = list(db.scalars(select(StoreReimbursementOpeningCutoff)))
        assert len(cutoffs) == 2
        assert {cutoff.starts_on for cutoff in cutoffs} == {date(2026, 7, 1)}
        assert {cutoff.ends_on for cutoff in cutoffs} == {date(2026, 7, 31)}
        assert {cutoff.reimbursed_amount for cutoff in cutoffs} == {Decimal("0.00")}

        supervisor = db.scalar(
            select(User).where(User.email == "luisa@example.com")
        )
        assert supervisor is not None
        assert supervisor.role == UserRole.authorizer
        assert supervisor.is_active is False
        area = db.scalar(
            select(AuthorizationArea).where(
                AuthorizationArea.normalized_name == "SUPERVISORES"
            )
        )
        assert area is not None
        assert db.scalar(
            select(func.count()).select_from(UserAuthorizationArea).where(
                UserAuthorizationArea.user_id == supervisor.id
            )
        ) == 1


def test_import_is_safe_to_rerun_and_does_not_modify_existing_rows(
    session_factory,
    monkeypatch,
) -> None:
    monkeypatch.setattr(initial_catalog_import, "cargar_base_tiendas", lambda _: _catalog())
    with session_factory() as db:
        first = initial_catalog_import.import_initial_catalog(db, "catalog.xlsx")
        db.commit()
        assert len(first.created_users) == 4

        v001 = db.scalar(
            select(StoreReimbursementOpeningCutoff)
            .join(Store)
            .where(Store.code == "V001")
        )
        assert v001 is not None
        v001.starts_on = date(2026, 6, 1)
        v001.ends_on = date(2026, 6, 30)
        v001.reimbursed_amount = Decimal("80.00")
        db.commit()

        second = initial_catalog_import.import_initial_catalog(db, "catalog.xlsx")
        db.commit()

        assert second.created_users == []
        assert second.created_stores == []
        assert second.created_assignments == 0
        assert len(second.skipped_users) == 6
        assert second.skipped_stores == ["V001", "V003"]
        assert db.scalar(select(func.count()).select_from(User)) == 4
        assert db.scalar(select(func.count()).select_from(Store)) == 2
        assert db.scalar(select(func.count()).select_from(StoreReimbursementOpeningCutoff)) == 2
        db.refresh(v001)
        assert v001.starts_on == date(2026, 6, 1)
        assert v001.ends_on == date(2026, 6, 30)
        assert v001.reimbursed_amount == Decimal("80.00")


def test_existing_user_is_not_changed_or_assigned(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(initial_catalog_import, "cargar_base_tiendas", lambda _: _catalog())
    with session_factory() as db:
        existing = User(
            email="luisa@example.com",
            full_name="Nombre Original",
            role=UserRole.authorizer,
            is_active=True,
        )
        db.add(existing)
        db.commit()

        result = initial_catalog_import.import_initial_catalog(db, "catalog.xlsx")
        db.commit()

        db.refresh(existing)
        assert existing.full_name == "Nombre Original"
        assert existing.is_active is True
        assert "luisa@example.com" in result.skipped_users
        assert db.scalar(
            select(func.count()).select_from(StoreUserAssignment).where(
                StoreUserAssignment.user_id == existing.id
            )
        ) == 0
