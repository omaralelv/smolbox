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
