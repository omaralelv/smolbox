import json
from pathlib import Path
from uuid import uuid4

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


def test_test_data_can_drive_end_user_backend_flow(client: TestClient) -> None:
    store = client.post(
        "/api/v1/stores/",
        json={"code": "E2E-001", "name": "Tienda E2E"},
    )
    assert store.status_code == 201, store.text

    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Agosto 2026 E2E",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-31",
        },
    )
    assert period.status_code == 201, period.text

    request = client.post(
        "/api/v1/reimbursement-requests/",
        json={
            "store_id": store.json()["id"],
            "period_id": period.json()["id"],
            "reported_total": "1850.50",
            "notes": "Prueba integral con datos demo CSV, CFDI y recibo.",
        },
    )
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]

    users = {
        role: _create_flow_user(client, role)
        for role in [
            "store",
            "authorizer",
            "accountant",
            "accounting_manager",
            "treasury",
            "director",
        ]
    }
    for role in ["store", "authorizer", "accountant", "accounting_manager"]:
        assignment = client.post(
            f"/api/v1/stores/{store.json()['id']}/users",
            json={"user_id": users[role], "role": role},
        )
        assert assignment.status_code == 201, assignment.text

    imported = client.post(
        f"/api/v1/reimbursement-requests/{request_id}/expenses/import",
        data={"dry_run": "false"},
        files={
            "file": (
                "expenses-authorization.csv",
                (DATA_DIR / "csv" / "expenses-authorization.csv").read_bytes(),
                "text/csv",
            )
        },
    )
    assert imported.status_code == 201, imported.text
    expenses = imported.json()["expenses"]
    assert len(expenses) == 3

    receipt_bytes = (DATA_DIR / "receipts" / "receipt-demo.pdf").read_bytes()
    for index, expense in enumerate(expenses, start=1):
        receipt = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            data={"attachment_type": "receipt"},
            files={"file": ("receipt-demo.pdf", receipt_bytes, "application/pdf")},
        )
        assert receipt.status_code == 201, receipt.text

        cfdi = client.post(
            f"/api/v1/expenses/{expense['id']}/cfdi/validate",
            files={
                "file": (
                    f"{expense['id']}.xml",
                    _cfdi_for_expense(expense, index=index),
                    "application/xml",
                )
            },
        )
        assert cfdi.status_code == 200, cfdi.text
        assert cfdi.json()["is_valid"] is True

    before_auth_review = client.post(
        f"/api/v1/reimbursement-requests/{request_id}/automated-review"
    )
    assert before_auth_review.status_code == 200, before_auth_review.text
    assert before_auth_review.json()["summary"]["missing_authorization_expense_ids"]

    _transition(client, request_id, users["store"], "submitted")
    _transition(client, request_id, users["authorizer"], "authorization_review")

    premature_authorization = client.post(
        f"/api/v1/reimbursement-requests/{request_id}/transition",
        json={
            "target_status": "authorized",
            "actor_user_id": users["authorizer"],
            "note": "Debe bloquear por autorizaciones pendientes.",
        },
    )
    assert premature_authorization.status_code == 409

    authorization_expenses = [expense for expense in expenses if expense["requires_authorization"]]
    assert len(authorization_expenses) == 2

    authorized_product = client.post(
        f"/api/v1/expenses/{authorization_expenses[0]['id']}/authorize",
        json={"actor_user_id": users["authorizer"], "note": "Producto autorizado."},
    )
    assert authorized_product.status_code == 200, authorized_product.text

    rejected_product = client.post(
        f"/api/v1/expenses/{authorization_expenses[1]['id']}/reject",
        json={
            "actor_user_id": users["authorizer"],
            "reason": "Producto no procede para reembolso.",
            "adjust_reported_total": True,
        },
    )
    assert rejected_product.status_code == 200, rejected_product.text

    summary = client.get(f"/api/v1/reimbursement-requests/{request_id}/validation-summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["reported_total"] == "600.50"
    assert summary.json()["calculated_total"] == "600.50"
    assert summary.json()["ready_for_accounting_approval"] is True
    assert len(summary.json()["rejected_expense_ids"]) == 1

    _transition(client, request_id, users["authorizer"], "authorized")
    _transition(client, request_id, users["accountant"], "under_accounting_review")
    _transition(client, request_id, users["accountant"], "accounting_reviewed")

    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{request_id}/sap-policy/prepare",
        json={
            "actor_user_id": users["accountant"],
            "reference": "SAP-E2E-001",
            "note": "Preparado en prueba integral.",
        },
    )
    assert sap_policy.status_code == 200, sap_policy.text
    assert sap_policy.json()["reference"] == "SAP-E2E-001"

    _transition(client, request_id, users["accounting_manager"], "accounting_manager_review")
    _transition(client, request_id, users["accounting_manager"], "accounting_manager_approved")
    _transition(client, request_id, users["treasury"], "treasury_review")
    _transition(client, request_id, users["treasury"], "direction_review")
    _transition(client, request_id, users["director"], "direction_approved")
    _transition(client, request_id, users["treasury"], "approved_for_payment")
    _transition(client, request_id, users["treasury"], "paid")
    closed = _transition(client, request_id, users["treasury"], "closed")
    assert closed["status"] == "closed"

    audit_events = client.get(f"/api/v1/reimbursement-requests/{request_id}/audit-events")
    assert audit_events.status_code == 200, audit_events.text
    audit_actions = {event["action"] for event in audit_events.json()}
    assert audit_actions >= {
        "request_created",
        "expenses_imported",
        "expense_attachment_uploaded",
        "expense_cfdi_validated",
        "automated_review_completed",
        "expense_authorized",
        "expense_authorization_rejected",
        "sap_policy_placeholder_prepared",
        "request_status_changed",
    }


def _create_flow_user(client: TestClient, role: str) -> str:
    response = client.post(
        "/api/v1/users/",
        json={
            "email": f"{role}.{uuid4().hex[:8]}@example.com",
            "full_name": f"Usuario {role}",
            "role": role,
            "password": "password123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _transition(
    client: TestClient,
    request_id: str,
    actor_user_id: str,
    target_status: str,
) -> dict:
    response = client.post(
        f"/api/v1/reimbursement-requests/{request_id}/transition",
        json={
            "target_status": target_status,
            "actor_user_id": actor_user_id,
            "note": f"Prueba integral hacia {target_status}.",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _cfdi_for_expense(expense: dict[str, object], *, index: int) -> bytes:
    template = (DATA_DIR / "cfdi" / "cfdi-valid-830-25.xml").read_text(encoding="utf-8")
    uuid = f"22222222-2222-4222-8{index:03d}-22222222222{index}"
    return (
        template.replace('Total="830.25"', f'Total="{expense["amount"]}"')
        .replace('Rfc="PCA9601011A1"', f'Rfc="{expense["supplier_tax_id"]}"')
        .replace(
            'UUID="11111111-1111-4111-8111-111111111111"',
            f'UUID="{uuid}"',
        )
        .encode("utf-8")
    )
