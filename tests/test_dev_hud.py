from fastapi.testclient import TestClient

from app.dev_hud.page import TEST_HUD_HTML


def test_dev_hud_html_uses_local_api() -> None:
    assert "Smolbox Dev HUD" in TEST_HUD_HTML
    assert "/api/v1" in TEST_HUD_HTML
    assert "/dev-hud/status" in TEST_HUD_HTML
    assert "Crear tienda" in TEST_HUD_HTML
    assert "Crear usuario" in TEST_HUD_HTML
    assert "Crear pago/gasto" in TEST_HUD_HTML


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
    assert scenario["summary"]["ready_for_accounting_approval"] is False
    assert len(scenario["expenses"]) == 2
    assert all(expense["has_receipt"] for expense in scenario["expenses"])
    assert not any(expense["has_current_valid_cfdi"] for expense in scenario["expenses"])

    submitted = client.post("/api/v1/dev-hud/transition/submitted")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["to_status"] == "submitted"

    review = client.post("/api/v1/dev-hud/transition/under_accounting_review")
    assert review.status_code == 200, review.text
    assert review.json()["to_status"] == "under_accounting_review"

    blocked = client.post("/api/v1/dev-hud/transition/accounting_approved")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    completed_cfdi = client.post("/api/v1/dev-hud/complete-cfdi")
    assert completed_cfdi.status_code == 200, completed_cfdi.text
    assert completed_cfdi.json()["cfdi_added"] == 2
    assert completed_cfdi.json()["scenario"]["summary"]["ready_for_accounting_approval"] is True

    approved = client.post("/api/v1/dev-hud/transition/accounting_approved")
    assert approved.status_code == 200, approved.text
    assert approved.json()["to_status"] == "accounting_approved"

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
