from fastapi.testclient import TestClient

from app.dev_hud.page import TEST_HUD_HTML


def test_dev_hud_html_uses_local_api() -> None:
    assert "Smolbox Dev HUD" in TEST_HUD_HTML
    assert "/api/v1" in TEST_HUD_HTML
    assert "/dev-hud/status" in TEST_HUD_HTML
    assert "Crear tienda" in TEST_HUD_HTML
    assert "Crear usuario" in TEST_HUD_HTML
    assert "Agregar gasto" in TEST_HUD_HTML
    assert "Personalizar escenario" in TEST_HUD_HTML
    assert "Solicitudes HUD" in TEST_HUD_HTML
    assert "scenarioList" in TEST_HUD_HTML
    assert "scenario-card" in TEST_HUD_HTML
    assert "selectedDevHudPath" in TEST_HUD_HTML
    assert "Vista producto" in TEST_HUD_HTML
    assert "Ventanas por rol" in TEST_HUD_HTML
    assert "productTabs" in TEST_HUD_HTML
    assert "productPreview" in TEST_HUD_HTML
    assert "product-tab" in TEST_HUD_HTML
    assert "product-window" in TEST_HUD_HTML
    assert "Flujo usuario final" in TEST_HUD_HTML
    assert "Sesión técnica" in TEST_HUD_HTML
    assert "Crear solicitud" in TEST_HUD_HTML
    assert "Revisar automáticamente" in TEST_HUD_HTML
    assert "Acciones disponibles" in TEST_HUD_HTML
    assert "Iniciar o cambiar sesión" in TEST_HUD_HTML
    assert "Cerrar sesión" in TEST_HUD_HTML
    assert "Ver mi cola" in TEST_HUD_HTML
    assert "Probar fuera de periodo" in TEST_HUD_HTML
    assert "Descargar recibo" in TEST_HUD_HTML
    assert "Reglas de negocio" in TEST_HUD_HTML
    assert "Guardar regla" in TEST_HUD_HTML
    assert "Quitar gasto" in TEST_HUD_HTML
    assert "Registrar pago" in TEST_HUD_HTML
    assert "scenarioSeedPayload" in TEST_HUD_HTML
    assert "specificErrorPayload" in TEST_HUD_HTML
    assert "writeErrorConsole" in TEST_HUD_HTML
    assert "HTTP_${error?.status" in TEST_HUD_HTML
    assert "jsonAuthRequest" in TEST_HUD_HTML
    assert "jsonAuthPatchRequest" in TEST_HUD_HTML
    assert "roleActions" in TEST_HUD_HTML
    assert "renderRoleActions" in TEST_HUD_HTML
    assert "executeAuthAction" in TEST_HUD_HTML
    assert "auth-action-btn" in TEST_HUD_HTML
    assert "/work-queue/me" in TEST_HUD_HTML
    assert "/business-rules/" in TEST_HUD_HTML
    assert "/download/me" in TEST_HUD_HTML
    assert "Autorizar gastos" in TEST_HUD_HTML
    assert "Rechazar producto" in TEST_HUD_HTML
    assert "Registrar pago" in TEST_HUD_HTML
    assert "executeUserFlowAction" in TEST_HUD_HTML
    assert "executeProductAction" in TEST_HUD_HTML
    assert "loginProductRole" in TEST_HUD_HTML
    assert "renderProductPreview" in TEST_HUD_HTML
    assert "Ejecutar automaticos" in TEST_HUD_HTML
    assert "Preparar póliza SAP" in TEST_HUD_HTML
    assert "Aprobar dirección" in TEST_HUD_HTML
    assert "Crear demo masivo" in TEST_HUD_HTML
    assert "/dev-hud/seed-bulk-demo" in TEST_HUD_HTML
    assert "seedBulkScenario" in TEST_HUD_HTML
    assert "expense-action-btn" in TEST_HUD_HTML
    assert "executeExpenseAction" in TEST_HUD_HTML
    assert "productExpenseActions" in TEST_HUD_HTML
    assert "HUD_EXPENSE_NOT_FOUND" in TEST_HUD_HTML


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

    automated_review = client.post("/api/v1/dev-hud/automated-review")
    assert automated_review.status_code == 200, automated_review.text
    assert automated_review.json()["review"]["overall_status"] == "blocked"
    assert any(
        step["code"] == "ocr_extraction"
        for step in automated_review.json()["review"]["automatic_steps"]
    )

    completed_cfdi = client.post("/api/v1/dev-hud/complete-cfdi")
    assert completed_cfdi.status_code == 200, completed_cfdi.text
    assert completed_cfdi.json()["cfdi_added"] == 2
    assert not completed_cfdi.json()["scenario"]["summary"]["missing_cfdi_expense_ids"]

    submitted = client.post("/api/v1/dev-hud/transition/submitted")
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["to_status"] == "submitted"

    late_cfdi = client.post("/api/v1/dev-hud/complete-cfdi")
    assert late_cfdi.status_code == 409
    assert late_cfdi.json()["detail"]["code"] == "REQUEST_NOT_EDITABLE"

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
    assert authorized_expenses.json()["scenario"]["summary"]["ready_for_accounting_approval"] is True

    authorized = client.post("/api/v1/dev-hud/transition/authorized")
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["to_status"] == "authorized"

    review = client.post("/api/v1/dev-hud/transition/under_accounting_review")
    assert review.status_code == 200, review.text
    assert review.json()["to_status"] == "under_accounting_review"

    accounting_reviewed = client.post("/api/v1/dev-hud/transition/accounting_reviewed")
    assert accounting_reviewed.status_code == 200, accounting_reviewed.text
    assert accounting_reviewed.json()["to_status"] == "accounting_reviewed"

    manager_blocked = client.post("/api/v1/dev-hud/transition/accounting_manager_review")
    assert manager_blocked.status_code == 409
    assert manager_blocked.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    accountant_login = client.post(
        "/api/v1/auth/login",
        json={"email": "hud.accountant@hud.smolbox.example.com", "password": "hud-password"},
    )
    assert accountant_login.status_code == 200, accountant_login.text

    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/sap-policy/prepare/me",
        headers={"Authorization": f"Bearer {accountant_login.json()['access_token']}"},
        json={"reference": "HUD-SAP-TOKEN", "note": "Preparado con token."},
    )
    assert sap_policy.status_code == 200, sap_policy.text
    assert sap_policy.json()["reference"] == "HUD-SAP-TOKEN"
    status_after_sap = client.get("/api/v1/dev-hud/status")
    assert status_after_sap.status_code == 200, status_after_sap.text
    assert status_after_sap.json()["scenario"]["sap_policy"]["is_prepared"] is True

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

    approved_for_payment = client.post("/api/v1/dev-hud/transition/approved_for_payment")
    assert approved_for_payment.status_code == 200, approved_for_payment.text
    assert approved_for_payment.json()["to_status"] == "approved_for_payment"

    direct_paid = client.post("/api/v1/dev-hud/transition/paid")
    assert direct_paid.status_code == 409
    assert direct_paid.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    treasury_login = client.post(
        "/api/v1/auth/login",
        json={"email": "hud.treasury@hud.smolbox.example.com", "password": "hud-password"},
    )
    assert treasury_login.status_code == 200, treasury_login.text
    wrong_amount_payment = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/payments/me",
        headers={"Authorization": f"Bearer {treasury_login.json()['access_token']}"},
        json={
            "amount": "1.00",
            "reference": "HUD-PAGO-MAL",
            "payment_method": "transfer",
            "note": "Debe fallar por monto incorrecto.",
        },
    )
    assert wrong_amount_payment.status_code == 409
    assert wrong_amount_payment.json()["detail"]["code"] == "PAYMENT_AMOUNT_MISMATCH"

    payment = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/payments/me",
        headers={"Authorization": f"Bearer {treasury_login.json()['access_token']}"},
        json={
            "reference": "HUD-PAGO-001",
            "payment_method": "transfer",
            "note": "Pago registrado desde HUD.",
        },
    )
    assert payment.status_code == 201, payment.text
    assert payment.json()["reference"] == "HUD-PAGO-001"

    duplicate_payment = client.post(
        f"/api/v1/reimbursement-requests/{scenario['request_id']}/payments/me",
        headers={"Authorization": f"Bearer {treasury_login.json()['access_token']}"},
        json={
            "reference": "HUD-PAGO-002",
            "payment_method": "transfer",
            "note": "Debe fallar por pago duplicado.",
        },
    )
    assert duplicate_payment.status_code == 409
    assert duplicate_payment.json()["detail"]["code"] == "PAYMENT_ALREADY_RECORDED"
    assert "suggestion" in duplicate_payment.json()["detail"]

    payments = client.get(f"/api/v1/reimbursement-requests/{scenario['request_id']}/payments")
    assert payments.status_code == 200, payments.text
    assert len(payments.json()) == 1

    closed = client.post("/api/v1/dev-hud/transition/closed")
    assert closed.status_code == 200, closed.text
    assert closed.json()["to_status"] == "closed"

    reset = client.post("/api/v1/dev-hud/reset-demo")
    assert reset.status_code == 200, reset.text
    assert reset.json()["deleted"]["reimbursement_requests"] == 1


def test_dev_hud_can_reject_one_authorization_expense(client: TestClient) -> None:
    seeded = client.post("/api/v1/dev-hud/seed-demo")
    assert seeded.status_code == 201, seeded.text

    submitted = client.post("/api/v1/dev-hud/transition/submitted")
    assert submitted.status_code == 200, submitted.text
    authorization_review = client.post("/api/v1/dev-hud/transition/authorization_review")
    assert authorization_review.status_code == 200, authorization_review.text

    rejected = client.post("/api/v1/dev-hud/reject-authorization-expense")
    assert rejected.status_code == 200, rejected.text
    scenario = rejected.json()["scenario"]
    assert scenario["summary"]["ready_for_authorization_approval"] is True
    assert len(scenario["summary"]["rejected_expense_ids"]) == 1
    assert any(expense["is_rejected"] for expense in scenario["expenses"])

    authorized = client.post("/api/v1/dev-hud/transition/authorized")
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["to_status"] == "authorized"

    final_status = client.get("/api/v1/dev-hud/status")
    assert final_status.status_code == 200, final_status.text
    assert final_status.json()["scenario"]["status"] == "authorized"


def test_dev_hud_demo_users_can_login_and_exposes_attachment_ids(
    client: TestClient,
) -> None:
    seeded = client.post("/api/v1/dev-hud/seed-demo")
    assert seeded.status_code == 201, seeded.text
    scenario = seeded.json()["scenario"]
    assert scenario["users"]["store"]["email"] == "hud.store@hud.smolbox.example.com"
    assert scenario["expenses"][0]["receipt_attachment_id"] is not None

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "hud.store@hud.smolbox.example.com", "password": "hud-password"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "store"


def test_dev_hud_creates_assigns_and_adds_payment(client: TestClient) -> None:
    seeded = client.post("/api/v1/dev-hud/seed-demo")
    assert seeded.status_code == 201, seeded.text

    store = client.post(
        "/api/v1/dev-hud/stores",
        json={
            "code": "HUD-099",
            "name": "HUD Tienda Asignable",
            "contact_email": "hud.tienda.asignable@hud.smolbox.example.com",
        },
    )
    assert store.status_code == 201, store.text
    store_id = store.json()["store"]["id"]

    user = client.post(
        "/api/v1/dev-hud/users",
        json={
            "email": "hud.contador.asignable@hud.smolbox.example.com",
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
            "contact_email": "hud.custom@hud.smolbox.example.com",
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


def test_dev_hud_can_target_multiple_scenarios_by_request_id(client: TestClient) -> None:
    first = client.post(
        "/api/v1/dev-hud/seed-demo",
        json={
            "reset_existing": True,
            "store_code": "HUD-MULTI-1",
            "store_name": "HUD Tienda Multiple 1",
            "contact_email": "hud.multi.1@hud.smolbox.example.com",
            "period_name": "HUD Agosto 2026",
        },
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["scenario"]["request_id"]

    second = client.post(
        "/api/v1/dev-hud/seed-demo",
        json={
            "reset_existing": False,
            "store_code": "HUD-MULTI-2",
            "store_name": "HUD Tienda Multiple 2",
            "contact_email": "hud.multi.2@hud.smolbox.example.com",
            "period_name": "HUD Agosto 2026",
        },
    )
    assert second.status_code == 201, second.text
    second_id = second.json()["scenario"]["request_id"]
    assert second_id != first_id

    status = client.get("/api/v1/dev-hud/status")
    assert status.status_code == 200, status.text
    request_ids = {item["request_id"] for item in status.json()["scenarios"]}
    assert {first_id, second_id}.issubset(request_ids)

    selected_first = client.get(f"/api/v1/dev-hud/status?request_id={first_id}")
    assert selected_first.status_code == 200, selected_first.text
    assert selected_first.json()["scenario"]["store_code"] == "HUD-MULTI-1"

    moved_first = client.post(f"/api/v1/dev-hud/transition/submitted?request_id={first_id}")
    assert moved_first.status_code == 200, moved_first.text
    assert moved_first.json()["scenario"]["store_code"] == "HUD-MULTI-1"
    assert moved_first.json()["to_status"] == "submitted"

    first_after_move = client.get(f"/api/v1/dev-hud/status?request_id={first_id}")
    assert first_after_move.status_code == 200, first_after_move.text
    assert first_after_move.json()["scenario"]["status"] == "submitted"

    second_after_move = client.get(f"/api/v1/dev-hud/status?request_id={second_id}")
    assert second_after_move.status_code == 200, second_after_move.text
    assert second_after_move.json()["scenario"]["store_code"] == "HUD-MULTI-2"
    assert second_after_move.json()["scenario"]["status"] == "draft"


def test_dev_hud_bulk_demo_seeds_realistic_queues(client: TestClient) -> None:
    seeded = client.post(
        "/api/v1/dev-hud/seed-bulk-demo",
        json={"reset_existing": True, "request_count": 15, "store_count": 5},
    )
    assert seeded.status_code == 201, seeded.text
    payload = seeded.json()
    assert payload["created"] == 15
    assert len(payload["scenarios"]) == 15

    statuses = {scenario["status"] for scenario in payload["scenarios"]}
    assert {
        "draft",
        "submitted",
        "authorization_review",
        "authorized",
        "under_accounting_review",
        "accounting_reviewed",
        "accounting_manager_review",
        "accounting_manager_approved",
        "treasury_review",
        "direction_review",
        "direction_approved",
        "approved_for_payment",
        "paid",
        "correction_required",
    }.issubset(statuses)

    status = client.get("/api/v1/dev-hud/status")
    assert status.status_code == 200, status.text
    assert status.json()["counts"]["reimbursement_requests"] == 15
    assert status.json()["counts"]["expenses"] == 45

    def role_queue_statuses(role: str) -> set[str]:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"hud.{role}@hud.smolbox.example.com",
                "password": "hud-password",
            },
        )
        assert login.status_code == 200, login.text
        queue = client.get(
            "/api/v1/work-queue/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert queue.status_code == 200, queue.text
        return {item["status"] for item in queue.json()}

    assert {"submitted", "authorization_review"}.issubset(role_queue_statuses("authorizer"))
    assert {"authorized", "under_accounting_review"}.issubset(role_queue_statuses("accountant"))
    assert {"accounting_reviewed", "accounting_manager_review"}.issubset(
        role_queue_statuses("accounting.manager")
    )
    assert {"direction_review"}.issubset(role_queue_statuses("director"))
    assert {
        "accounting_manager_approved",
        "treasury_review",
        "direction_approved",
        "approved_for_payment",
        "paid",
    }.issubset(role_queue_statuses("treasury"))

    paid_request_id = next(
        scenario["request_id"] for scenario in payload["scenarios"] if scenario["status"] == "paid"
    )
    payments = client.get(f"/api/v1/reimbursement-requests/{paid_request_id}/payments")
    assert payments.status_code == 200, payments.text
    assert len(payments.json()) == 1
    assert payments.json()[0]["reference"].startswith("HUD-BULK-PAGO-")
