from fastapi.testclient import TestClient


def _admin_headers(client: TestClient) -> dict[str, str]:
    created = client.post(
        "/api/v1/users/",
        json={
            "email": "rules.admin@example.com",
            "full_name": "Rules Admin",
            "role": "admin",
            "password": "secret-password",
        },
    )
    assert created.status_code == 201, created.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "rules.admin@example.com", "password": "secret-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_business_rules_can_be_listed_and_updated_by_admin(client: TestClient) -> None:
    rules = client.get("/api/v1/business-rules/")
    assert rules.status_code == 200, rules.text
    codes = {rule["code"] for rule in rules.json()}
    assert {
        "authorization_threshold",
        "require_cfdi_for_accounting",
        "block_out_of_period_expenses",
        "auto_adjust_total_on_removed_expense",
    } <= codes

    unauthorized = client.patch(
        "/api/v1/business-rules/authorization_threshold",
        json={"value": {"amount": "1500.00", "currency": "MXN"}},
    )
    assert unauthorized.status_code == 401

    updated = client.patch(
        "/api/v1/business-rules/authorization_threshold",
        headers=_admin_headers(client),
        json={"value": {"amount": "1500.00", "currency": "MXN"}, "is_active": True},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["value"]["amount"] == "1500.00"
