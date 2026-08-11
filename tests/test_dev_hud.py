from fastapi.testclient import TestClient

from app.dev_hud.page import TEST_HUD_HTML


def test_dev_hud_html_uses_local_api() -> None:
    assert "Smolbox Dev HUD" in TEST_HUD_HTML
    assert "/api/v1" in TEST_HUD_HTML
    assert "/dev-hud/status" in TEST_HUD_HTML
    assert "Crear tienda" in TEST_HUD_HTML
    assert "Crear usuario" in TEST_HUD_HTML
    assert "Crear pago/gasto" in TEST_HUD_HTML
    assert "Personalizar escenario" in TEST_HUD_HTML
    assert "scenarioSeedPayload" in TEST_HUD_HTML
    assert "Autorizar gastos" in TEST_HUD_HTML
    assert "Aprobar dirección" in TEST_HUD_HTML


def test_dev_hud_seeds_and_exercises_workflow(client: TestClient) -> None:
    initial_status = client.get("/api/v1/dev-hud/status")
    assert initial_status.status_code == 200, initial_status.text
    assert initial_status.json()["scenario"]["exists"] is False

    seeded = client.post("/api/v1/dev-hud/seed-demo")
    assert seeded.status_code == 201, seeded.text
    scenario = seeded.json()["scenario"]
    assert scenario["exists"] is True
    assert scenario["status"] == "draft"
    assert scenario["summary"]["ready_for_submission"] is True
    assert scenario["summary"]["ready_for_authorization_approval"] is False
    assert scenario["summary"]["ready_for_accounting_approval"] is False
    assert len(scenario["expenses"]) == 2
    assert all(expense["has_receipt"] for expense in scenario["expenses"])
    assert any(expense["requires_authorization"] for expense in scenario["expenses"])
    assert not any(expense["has_current_valid_cfdi"] for expense in scenario["expenses"])

    submitted = client.post("/api/v1/dev-hud/transition/submitted")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["to_status"] == "submitted"

    authorization_review = client.post("/api/v1/dev-hud/transition/authorization_review")
    assert authorization_review.status_code == 200, authorization_review.text
    assert authorization_review.json()["to_status"] == "authorization_review"

    blocked = client.post("/api/v1/dev-hud/transition/authorized")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    authorized_expenses = client.post("/api/v1/dev-hud/authorize-expenses")
    assert authorized_expenses.status_code == 200, authorized_expenses.text
    assert authorized_expenses.json()["authorized"] == 1
    assert (
        authorized_expenses.json()["scenario"]["summary"]["ready_for_authorization_approval"]
        is True
    )

    authorized = client.post("/api/v1/dev-hud/transition/authorized")
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["to_status"] == "authorized"

    review = client.post("/api/v1/dev-hud/transition/under_accounting_review")
    assert review.status_code == 200, review.text
    assert review.json()["to_status"] == "under_accounting_review"

    accounting_blocked = client.post("/api/v1/dev-hud/transition/accounting_reviewed")
    assert accounting_blocked.status_code == 409
    assert accounting_blocked.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    completed_cfdi = client.post("/api/v1/dev-hud/complete-cfdi")
    assert completed_cfdi.status_code == 200, completed_cfdi.text
    assert completed_cfdi.json()["cfdi_added"] == 2
    assert completed_cfdi.json()["scenario"]["summary"]["ready_for_accounting_approval"] is True

    accounting_reviewed = client.post("/api/v1/dev-hud/transition/accounting_reviewed")
    assert accounting_reviewed.status_code == 200, accounting_reviewed.text
    assert accounting_reviewed.json()["to_status"] == "accounting_reviewed"

    manager_review = client.post("/api/v1/dev-hud/transition/accounting_manager_review")
    assert manager_review.status_code == 200, manager_review.text
    assert manager_review.json()["to_status"] == "accounting_manager_review"

    manager_approved = client.post("/api/v1/dev-hud/transition/accounting_manager_approved")
    assert manager_approved.status_code == 200, manager_approved.text
    assert manager_approved.json()["to_status"] == "accounting_manager_approved"

    treasury_review = client.post("/api/v1/dev-hud/transition/treasury_review")
    assert treasury_review.status_code == 200, treasury_review.text
    assert treasury_review.json()["to_status"] == "treasury_review"

    direction_review = client.post("/api/v1/dev-hud/transition/direction_review")
    assert direction_review.status_code == 200, direction_review.text
    assert direction_review.json()["to_status"] == "direction_review"

    direction_approved = client.post("/api/v1/dev-hud/transition/direction_approved")
    assert direction_approved.status_code == 200, direction_approved.text
    assert direction_approved.json()["to_status"] == "direction_approved"

    reset = client.post("/api/v1/dev-hud/reset-demo")
    assert reset.status_code == 200, reset.text
    assert reset.json()["deleted"]["reimbursement_requests"] == 1

    final_status = client.get("/api/v1/dev-hud/status")
    assert final_status.status_code == 200, final_status.text
    assert final_status.json()["scenario"]["exists"] is False


def test_dev_hud_creates_assigns_and_adds_payment(client: TestClient) -> None:
    seeded = client.post("/api/v1/dev-hud/seed-demo")
    assert seeded.status_code == 201, seeded.text

    store = client.post(
        "/api/v1/dev-hud/stores",
        json={
            "code": "HUD-099",
            "name": "HUD Tienda Asignable",
            "contact_email": "hud.tienda.asignable@hud.smolbox.local",
        },
    )
    assert store.status_code == 201, store.text
    store_id = store.json()["store"]["id"]

    user = client.post(
        "/api/v1/dev-hud/users",
        json={
            "email": "hud.contador.asignable@hud.smolbox.local",
            "full_name": "HUD Contador Asignable",
            "role": "accountant",
        },
    )
    assert user.status_code == 201, user.text
    user_id = user.json()["user"]["id"]

    assignment = client.post(
        "/api/v1/dev-hud/assign-user",
        json={"store_id": store_id, "user_id": user_id},
    )
    assert assignment.status_code == 200, assignment.text
    assert assignment.json()["assigned_field"] == "assigned_accountant"
    assert assignment.json()["store"]["assigned_accountant"] == "HUD Contador Asignable"

    payment = client.post(
        "/api/v1/dev-hud/payments",
        json={
            "merchant": "HUD Pago Manual",
            "amount": "250.00",
            "spent_on": "2026-08-17",
            "category": "comida",
            "keep_reported_total_balanced": True,
        },
    )
    assert payment.status_code == 201, payment.text
    scenario = payment.json()["scenario"]
    assert scenario["summary"]["reported_total"] == "1750.00"
    assert scenario["summary"]["calculated_total"] == "1750.00"
    assert len(scenario["expenses"]) == 3
    assert any(expense["merchant"] == "HUD Pago Manual" for expense in scenario["expenses"])


def test_dev_hud_seeds_custom_scenario(client: TestClient) -> None:
    seeded = client.post(
        "/api/v1/dev-hud/seed-demo",
        json={
            "reset_existing": True,
            "store_code": "HUD-CUSTOM",
            "store_name": "HUD Tienda Custom",
            "contact_email": "hud.custom@hud.smolbox.local",
            "period_name": "HUD Septiembre 2026",
            "starts_on": "2026-09-01",
            "ends_on": "2026-09-30",
            "reported_total": "333.00",
            "expenses": [
                {
                    "merchant": "HUD Cafe Custom",
                    "amount": "111.00",
                    "spent_on": "2026-09-05",
                    "category": "comida",
                    "supplier_tax_id": "XAXX010101000",
                    "requires_authorization": False,
                },
                {
                    "merchant": "HUD Taxi Custom",
                    "amount": "222.00",
                    "spent_on": "2026-09-06",
                    "category": "transporte",
                    "supplier_tax_id": "XEXX010101000",
                    "requires_authorization": True,
                },
            ],
        },
    )
    assert seeded.status_code == 201, seeded.text

    scenario = seeded.json()["scenario"]
    assert scenario["store_code"] == "HUD-CUSTOM"
    assert scenario["store_name"] == "HUD Tienda Custom"
    assert scenario["period_name"] == "HUD Septiembre 2026"
    assert scenario["summary"]["reported_total"] == "333.00"
    assert scenario["summary"]["calculated_total"] == "333.00"
    assert [expense["merchant"] for expense in scenario["expenses"]] == [
        "HUD Cafe Custom",
        "HUD Taxi Custom",
    ]
    assert scenario["summary"]["ready_for_authorization_approval"] is False

    status = client.get("/api/v1/dev-hud/status")
    assert status.status_code == 200, status.text
    assert status.json()["scenario"]["store_code"] == "HUD-CUSTOM"
