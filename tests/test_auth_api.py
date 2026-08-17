from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def test_user_can_login_and_read_me(client: TestClient) -> None:
    created = client.post(
        "/api/v1/users/",
        json={
            "email": "login@example.com",
            "full_name": "Login Demo",
            "role": "accountant",
            "password": "secret-password",
        },
    )
    assert created.status_code == 201, created.text
    assert "password" not in created.json()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "secret-password"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "login@example.com"


def test_login_rejects_bad_password(client: TestClient) -> None:
    created = client.post(
        "/api/v1/users/",
        json={
            "email": "bad-login@example.com",
            "full_name": "Bad Login Demo",
            "role": "store",
            "password": "correct-password",
        },
    )
    assert created.status_code == 201, created.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "bad-login@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401
    assert login.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_user_context_returns_assigned_store_and_current_period(client: TestClient) -> None:
    today = datetime.now(UTC).date()
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "context.store@example.com",
            "full_name": "Context Store",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text

    store = client.post(
        "/api/v1/stores/",
        json={
            "code": "T777",
            "name": "Tienda Contexto",
            "manager_name": "Karen Ponce Hernandez",
            "bank_account": "101328508",
            "state_region": "CDMX",
        },
    )
    assert store.status_code == 201, store.text

    assignment = client.post(
        f"/api/v1/stores/{store.json()['id']}/users",
        json={"user_id": user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text

    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Periodo Contexto",
            "starts_on": (today - timedelta(days=3)).isoformat(),
            "ends_on": (today + timedelta(days=3)).isoformat(),
        },
    )
    assert period.status_code == 201, period.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "context.store@example.com", "password": "secret-password"},
    )
    assert login.status_code == 200, login.text

    context = client.get(
        "/api/v1/auth/me/context",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert context.status_code == 200, context.text
    body = context.json()
    assert body["user"]["email"] == "context.store@example.com"
    assert body["active_store"]["code"] == "T777"
    assert body["active_store"]["manager_name"] == "Karen Ponce Hernandez"
    assert body["active_store"]["bank_account"] == "101328508"
    assert body["active_store"]["state_region"] == "CDMX"
    assert body["current_period"]["id"] == period.json()["id"]
