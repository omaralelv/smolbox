from fastapi.testclient import TestClient


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
