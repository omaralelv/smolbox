from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1.endpoints import users as users_endpoint
from app.models.store import Store, StoreUserAssignment
from app.models.store_reimbursement_opening_cutoff import (
    StoreReimbursementOpeningCutoff,
)
from app.models.user import User


def test_create_store_user_creates_store_cutoff_and_assignment_atomically(
    client: TestClient,
    session_factory,
) -> None:
    response = client.post(
        "/api/v1/users/store",
        json={
            "code": " t214 ",
            "full_name": "San Francisco",
            "email": " SAN.FRANCISCO@EXAMPLE.COM ",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["store"]["code"] == "T214"
    assert response.json()["store"]["name"] == "San Francisco"
    assert response.json()["user"]["full_name"] == "San Francisco"
    assert response.json()["user"]["role"] == "store"
    assert response.json()["user"]["email"] == "san.francisco@example.com"
    assert response.json()["assignment"]["role"] == "store"

    with session_factory() as db:
        store = db.scalar(select(Store).where(Store.code == "T214"))
        user = db.scalar(select(User).where(User.email == "san.francisco@example.com"))
        assert store is not None
        assert user is not None

        cutoff = db.scalar(
            select(StoreReimbursementOpeningCutoff).where(
                StoreReimbursementOpeningCutoff.store_id == store.id
            )
        )
        assignment = db.scalar(
            select(StoreUserAssignment).where(
                StoreUserAssignment.store_id == store.id,
                StoreUserAssignment.user_id == user.id,
            )
        )
        assert cutoff is not None
        assert cutoff.starts_on == date(2026, 7, 1)
        assert cutoff.ends_on == date(2026, 7, 31)
        assert cutoff.reimbursed_amount == Decimal("0.00")
        assert assignment is not None
        assert assignment.is_active is True


def test_create_store_user_rejects_duplicate_code_and_email(
    client: TestClient,
    session_factory,
) -> None:
    invalid_code = client.post(
        "/api/v1/users/store",
        json={
            "code": "T21",
            "full_name": "Tienda Inválida",
            "email": "store.invalid@example.com",
        },
    )
    assert invalid_code.status_code == 422

    first = client.post(
        "/api/v1/users/store",
        json={
            "code": "T215",
            "full_name": "Tienda Uno",
            "email": "store.user.one@example.com",
        },
    )
    assert first.status_code == 201, first.text

    duplicate_code = client.post(
        "/api/v1/users/store",
        json={
            "code": "t215",
            "full_name": "Tienda Dos",
            "email": "store.user.two@example.com",
        },
    )
    assert duplicate_code.status_code == 409
    assert duplicate_code.json()["detail"]["code"] == "DUPLICATE_STORE_CODE"

    duplicate_email = client.post(
        "/api/v1/users/store",
        json={
            "code": "T216",
            "full_name": "Tienda Tres",
            "email": "store.user.one@example.com",
        },
    )
    assert duplicate_email.status_code == 409
    assert duplicate_email.json()["detail"]["code"] == "DUPLICATE_USER_EMAIL"

    with session_factory() as db:
        assert db.scalar(select(Store).where(Store.code == "T216")) is None
        assert db.scalar(select(User).where(User.email == "store.user.two@example.com")) is None


def test_create_store_user_rolls_back_if_cognito_sync_fails(
    client: TestClient,
    session_factory,
    monkeypatch,
) -> None:
    def fail_cognito_sync(*args, **kwargs):
        raise HTTPException(
            status_code=502,
            detail={"code": "COGNITO_SYNC_FAILED", "message": "Cognito unavailable"},
        )

    monkeypatch.setattr(users_endpoint, "_ensure_cognito_user", fail_cognito_sync)

    response = client.post(
        "/api/v1/users/store",
        json={
            "code": "T217",
            "full_name": "Tienda Rollback",
            "email": "store.rollback@example.com",
        },
    )

    assert response.status_code == 502
    with session_factory() as db:
        assert db.scalar(select(Store).where(Store.code == "T217")) is None
        assert db.scalar(select(User).where(User.email == "store.rollback@example.com")) is None
        assert db.scalar(select(StoreUserAssignment)) is None
        assert db.scalar(select(StoreReimbursementOpeningCutoff)) is None


def test_store_code_accepts_free_form_values_and_rejects_repeats(client: TestClient) -> None:
    first = client.post(
        "/api/v1/stores/",
        json={
            "code": " tienda-001 ",
            "name": "Tienda Libre Uno",
            "contact_email": " contacto libre ",
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["code"] == "tienda-001"
    assert first.json()["contact_email"] == "contacto libre"

    second = client.post(
        "/api/v1/stores/",
        json={"code": "tienda-001", "name": "Tienda Libre Dos"},
    )
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "STORE_VALUE_INVALID"


def test_can_assign_active_user_to_store(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "assigned.accountant@example.com",
            "full_name": "Assigned Accountant",
            "role": "accountant",
        },
    )
    assert user.status_code == 201, user.text

    assigned = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": user.json()["id"], "role": "accountant"},
    )
    assert assigned.status_code == 201, assigned.text
    assert assigned.json()["store_id"] == base_records["store_id"]
    assert assigned.json()["user_id"] == user.json()["id"]
    assert assigned.json()["role"] == "accountant"

    listed = client.get(f"/api/v1/stores/{base_records['store_id']}/users")
    assert listed.status_code == 200, listed.text
    assert [item["user_id"] for item in listed.json()] == [user.json()["id"]]


def test_assignment_role_must_match_user_role(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "role.mismatch@example.com",
            "full_name": "Role Mismatch",
            "role": "store",
        },
    )
    assert user.status_code == 201, user.text

    assigned = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": user.json()["id"], "role": "accountant"},
    )
    assert assigned.status_code == 422
    assert assigned.json()["detail"]["code"] == "ASSIGNMENT_ROLE_MISMATCH"
