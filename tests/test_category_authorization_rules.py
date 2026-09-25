from fastapi.testclient import TestClient


def test_papeleria_threshold_routes_to_insumos(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Papeleria Demo",
            "amount": "600.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Papeleria",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["requires_authorization"] is True
    assert body["authorization_area_name"] == "Insumos"


def test_papeleria_below_threshold_does_not_require_authorization(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Papeleria Demo",
            "amount": "599.99",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Papelería",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["requires_authorization"] is False
    assert body["authorization_area_name"] is None


def test_insumo_always_routes_to_insumos(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Insumo Demo",
            "amount": "1.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Insumo",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["requires_authorization"] is True
    assert body["authorization_area_name"] == "Insumos"


def test_agua_never_requires_category_authorization(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Servicio de agua demo",
            "amount": "5000.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Agua",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["requires_authorization"] is False
    assert body["authorization_area_name"] is None
