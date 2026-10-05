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
            "previous_reimbursement_starts_on": "2026-09-01",
            "previous_reimbursement_ends_on": "2026-09-30",
        },
    )
    assert second_request.status_code == 201, second_request.text
    assert second_request.json()["id"] != base_records["request_id"]
    assert second_request.json()["folio"] != ""
    assert second_request.json()["previous_reimbursement_starts_on"] == "2026-07-01"
    assert second_request.json()["previous_reimbursement_ends_on"] == "2026-07-31"

    outside_period = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor fuera de periodo",
            "amount": "50.00",
            "currency": "MXN",
            "spent_on": "2026-07-30",
        },
    )
    assert outside_period.status_code == 422
    assert outside_period.json()["detail"]["code"] == "EXPENSE_OUTSIDE_PERIOD"
    assert outside_period.json()["detail"]["message"] == "El gasto está fuera de periodo."
    assert "2026" not in outside_period.text

    valid = create_expense(client, base_records)
    assert valid["period_id"] == base_records["period_id"]

    on_previous_close = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Gasto en el día de cierre previo",
            "amount": "25.00",
            "currency": "MXN",
            "spent_on": "2026-07-31",
        },
    )
    assert on_previous_close.status_code == 201, on_previous_close.text


def test_expense_edit_cannot_move_date_before_previous_close(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records)

    response = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        json={"spent_on": "2026-07-30"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "EXPENSE_OUTSIDE_PERIOD",
        "message": "El gasto está fuera de periodo.",
    }


def test_request_previous_close_cannot_be_changed(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    response = client.patch(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}",
        json={"previous_reimbursement_ends_on": "2026-01-01"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "REIMBURSEMENT_PERIOD_END_IMMUTABLE",
        "message": "No se puede modificar este campo.",
    }
