import json
from pathlib import Path

from fastapi.testclient import TestClient

DATA_DIR = Path(__file__).resolve().parents[1] / "docs" / "test-data"


def test_hud_test_scenarios_can_seed_demo_data(client: TestClient) -> None:
    for scenario_path in sorted((DATA_DIR / "scenarios").glob("*.json")):
        payload = json.loads(scenario_path.read_text(encoding="utf-8"))

        response = client.post("/api/v1/dev-hud/seed-demo", json=payload)

        assert response.status_code == 201, f"{scenario_path.name}: {response.text}"
        scenario = response.json()["scenario"]
        assert scenario["exists"] is True
        assert scenario["store_code"] == payload["store_code"]


def test_csv_test_data_imports_or_fails_as_expected(client: TestClient) -> None:
    seeded = client.post(
        "/api/v1/dev-hud/seed-demo",
        json=json.loads(
            (DATA_DIR / "scenarios" / "hud-approval-flow.json").read_text(encoding="utf-8")
        ),
    )
    assert seeded.status_code == 201, seeded.text
    request_id = seeded.json()["scenario"]["request_id"]

    for csv_name in ["expenses-valid.csv", "expenses-authorization.csv"]:
        csv_content = (DATA_DIR / "csv" / csv_name).read_bytes()
        response = client.post(
            f"/api/v1/reimbursement-requests/{request_id}/expenses/import",
            data={"dry_run": "true"},
            files={"file": (csv_name, csv_content, "text/csv")},
        )

        assert response.status_code == 201, f"{csv_name}: {response.text}"
        assert response.json()["dry_run"] is True
        assert response.json()["imported_count"] > 0

    invalid_content = (DATA_DIR / "csv" / "expenses-invalid.csv").read_bytes()
    invalid = client.post(
        f"/api/v1/reimbursement-requests/{request_id}/expenses/import",
        data={"dry_run": "true"},
        files={"file": ("expenses-invalid.csv", invalid_content, "text/csv")},
    )

    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "IMPORT_VALIDATION_FAILED"


def test_cfdi_and_receipt_test_data_are_accepted(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Papeleria Centro SA",
            "amount": "830.25",
            "currency": "MXN",
            "spent_on": "2026-08-05",
            "category": "papeleria",
            "supplier_tax_id": "PCA9601011A1",
        },
    )
    assert expense.status_code == 201, expense.text
    expense_id = expense.json()["id"]

    receipt = client.post(
        f"/api/v1/expenses/{expense_id}/attachments",
        data={"attachment_type": "receipt"},
        files={
            "file": (
                "receipt-demo.pdf",
                (DATA_DIR / "receipts" / "receipt-demo.pdf").read_bytes(),
                "application/pdf",
            )
        },
    )
    assert receipt.status_code == 201, receipt.text

    valid_cfdi = client.post(
        f"/api/v1/expenses/{expense_id}/cfdi/validate",
        files={
            "file": (
                "cfdi-valid-830-25.xml",
                (DATA_DIR / "cfdi" / "cfdi-valid-830-25.xml").read_bytes(),
                "application/xml",
            )
        },
    )
    assert valid_cfdi.status_code == 200, valid_cfdi.text
    assert valid_cfdi.json()["is_valid"] is True

    mismatch_expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Papeleria Centro SA",
            "amount": "830.25",
            "currency": "MXN",
            "spent_on": "2026-08-05",
            "category": "papeleria",
            "supplier_tax_id": "PCA9601011A1",
        },
    )
    assert mismatch_expense.status_code == 201, mismatch_expense.text

    mismatch_cfdi = client.post(
        f"/api/v1/expenses/{mismatch_expense.json()['id']}/cfdi/validate",
        files={
            "file": (
                "cfdi-total-mismatch.xml",
                (DATA_DIR / "cfdi" / "cfdi-total-mismatch.xml").read_bytes(),
                "application/xml",
            )
        },
    )
    assert mismatch_cfdi.status_code == 200, mismatch_cfdi.text
    assert mismatch_cfdi.json()["is_valid"] is False
    assert "total_mismatch" in {issue["code"] for issue in mismatch_cfdi.json()["issues"]}
