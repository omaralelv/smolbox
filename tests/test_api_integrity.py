from conftest import create_expense
from fastapi.testclient import TestClient


def test_allows_multiple_requests_per_store_period_and_rejects_expense_outside_period(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    second_request = client.post(
        "/api/v1/reimbursement-requests/",
        json={
            "store_id": base_records["store_id"],
            "period_id": base_records["period_id"],
            "reported_total": "50.00",
        },
    )
    assert second_request.status_code == 201, second_request.text
    assert second_request.json()["id"] != base_records["request_id"]
    assert second_request.json()["folio"] != ""

    outside_period = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor fuera de periodo",
            "amount": "50.00",
            "currency": "MXN",
            "spent_on": "2026-09-01",
        },
    )
    assert outside_period.status_code == 422
    assert outside_period.json()["detail"]["code"] == "EXPENSE_OUTSIDE_PERIOD"

    valid = create_expense(client, base_records)
    assert valid["period_id"] == base_records["period_id"]
