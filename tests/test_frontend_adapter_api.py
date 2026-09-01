from conftest import create_expense
from fastapi.testclient import TestClient


def test_frontend_context_and_bandeja_use_ui_shape(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "frontend.store@example.com",
            "full_name": "Frontend Store",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text
    assignment = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    assert expense["id"]
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    headers = _auth_headers(client, "frontend.store@example.com")

    context = client.get("/api/v1/frontend/context/me", headers=headers)
    assert context.status_code == 200, context.text
    context_body = context.json()
    assert context_body["currentRole"] == "tienda"
    assert context_body["backendRole"] == "store"
    assert context_body["tienda"] == "T001"

    bandeja = client.get("/api/v1/frontend/bandeja/me", headers=headers)
    assert bandeja.status_code == 200, bandeja.text
    assert bandeja.json() == []

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        user.json()["id"],
    )
    assert submitted.status_code == 200, submitted.text

    bandeja_enviada = client.get("/api/v1/frontend/bandeja/me", headers=headers)
    assert bandeja_enviada.status_code == 200, bandeja_enviada.text
    items = bandeja_enviada.json()
    assert len(items) == 1
    item = items[0]
    assert item["id"] == item["folio"]
    assert item["backendId"] == base_records["request_id"]
    assert item["tienda"] == "T001"
    assert item["status"] == "En revisión"
    assert item["montoTotal"] == 1500.0
    assert item["gastos"][0]["monto"] == 1500.0
    assert item["gastos"][0]["tipo"]
    assert "backendId" in item["gastos"][0]
    assert item["availableActions"] == []
    assert item["actionLabels"] == {}


def test_frontend_can_create_request_and_lookup_by_folio(client: TestClient) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "frontend.create@example.com",
            "full_name": "Frontend Create",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text
    store = client.post(
        "/api/v1/stores/",
        json={
            "code": "T998",
            "name": "Tienda Frontend",
            "manager_name": "Karen Ponce Hernandez",
            "bank_account": "101328508",
            "state_region": "CDMX",
        },
    )
    assert store.status_code == 201, store.text
    assignment = client.post(
        f"/api/v1/stores/{store.json()['id']}/users",
        json={"user_id": user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text
    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Agosto Frontend",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-31",
        },
    )
    assert period.status_code == 201, period.text

    headers = _auth_headers(client, "frontend.create@example.com")
    created = client.post(
        "/api/v1/frontend/solicitudes/me",
        headers=headers,
        json={
            "tienda": "T998",
            "montoTotal": "56.00",
            "gastos": [
                {
                    "fecha": "07/08/2026",
                    "categoria": "Papelería",
                    "monto": "56.00",
                    "folio": "5FB2822E-396D-4725-8521-CDC4BDD20CCF",
                    "cfdiSubtotal": "48.28",
                    "cfdiTotal": "56.00",
                    "cfdiTaxAmount": "7.72",
                    "cfdiTaxRate": "16.00",
                    "cfdiCurrency": "MXN",
                    "observaciones": "Compra demo",
                    "requiresAuthorization": True,
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["id"].startswith("T998-")
    assert created_body["tienda"] == "T998"
    assert created_body["gerente"] == "Karen Ponce Hernandez"
    assert created_body["cuentaBancaria"] == "101328508"
    assert created_body["montoTotal"] == 56.0
    assert created_body["gastos"][0]["nombre"] == "Gasto - Papelería"
    assert created_body["gastos"][0]["folio"] == "5FB2822E-396D-4725-8521-CDC4BDD20CCF"
    assert created_body["gastos"][0]["cfdiSubtotal"] == 48.28
    assert created_body["gastos"][0]["cfdiTaxAmount"] == 7.72
    assert created_body["gastos"][0]["cfdiTaxRate"] == 16.0
    assert created_body["gastos"][0]["cfdiCurrency"] == "MXN"
    assert created_body["gastos"][0]["requiresAuthorization"] is True

    detail = client.get(
        f"/api/v1/frontend/solicitudes/{created_body['folio']}/me",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["backendId"] == created_body["backendId"]


def test_frontend_taxi_expense_routes_request_to_authorization(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    store_user_id = _create_user(client, "store", "frontend.taxi.store@example.com")
    authorizer_user_id = _create_user(
        client,
        "authorizer",
        "frontend.taxi.authorizer@example.com",
    )
    accountant_user_id = _create_user(
        client,
        "accountant",
        "frontend.taxi.accountant@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    store_headers = _auth_headers(client, "frontend.taxi.store@example.com")
    created = client.post(
        "/api/v1/frontend/solicitudes/me",
        headers=store_headers,
        json={
            "tienda": "T001",
            "montoTotal": "1500.00",
            "gastos": [
                {
                    "fecha": "07/08/2026",
                    "categoria": "Pasajes y Taxis",
                    "monto": "1500.00",
                    "observaciones": "Traslado operativo",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    created_expense = created_body["gastos"][0]
    assert created_expense["requiresAuthorization"] is True
    assert created_expense["autorizacion"] == ""

    _attach_valid_cfdi(
        client,
        created_expense["backendId"],
        "1500.00",
        uuid="66666666-6666-4666-8666-666666666666",
    )

    submitted = _transition(
        client,
        created_body["backendId"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    authorizer_headers = _auth_headers(client, "frontend.taxi.authorizer@example.com")
    authorizer_queue = client.get("/api/v1/frontend/bandeja/me", headers=authorizer_headers)
    assert authorizer_queue.status_code == 200, authorizer_queue.text
    assert [item["backendId"] for item in authorizer_queue.json()] == [created_body["backendId"]]

    accountant_headers = _auth_headers(client, "frontend.taxi.accountant@example.com")
    accountant_queue = client.get("/api/v1/frontend/bandeja/me", headers=accountant_headers)
    assert accountant_queue.status_code == 200, accountant_queue.text
    assert accountant_queue.json() == []


def test_frontend_accounting_actions_follow_sap_policy_order(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    store_user_id = _create_user(client, "store", "frontend.sap.store@example.com")
    accountant_user_id = _create_user(
        client,
        "accountant",
        "frontend.sap.accountant@example.com",
    )
    manager_user_id = _create_user(
        client,
        "accounting_manager",
        "frontend.sap.manager@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")
    _assign_user_to_store(
        client,
        base_records["store_id"],
        manager_user_id,
        "accounting_manager",
    )

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    store_headers = _auth_headers(client, "frontend.sap.store@example.com")
    store_bandeja = client.get("/api/v1/frontend/bandeja/me", headers=store_headers)
    assert store_bandeja.status_code == 200, store_bandeja.text
    assert any(
        item["backendId"] == base_records["request_id"] and item["status"] == "En revisión"
        for item in store_bandeja.json()
    )

    accountant_headers = _auth_headers(client, "frontend.sap.accountant@example.com")
    submitted_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=accountant_headers,
    )
    assert submitted_detail.status_code == 200, submitted_detail.text
    assert submitted_detail.json()["availableActions"] == ["start_accounting_review"]

    review = _transition(
        client,
        base_records["request_id"],
        "under_accounting_review",
        accountant_user_id,
    )
    assert review.status_code == 200, review.text

    review_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=accountant_headers,
    )
    assert review_detail.status_code == 200, review_detail.text
    assert "mark_accounting_reviewed" in review_detail.json()["availableActions"]
    assert "prepare_sap_policy" not in review_detail.json()["availableActions"]

    reviewed = _transition(
        client,
        base_records["request_id"],
        "accounting_reviewed",
        accountant_user_id,
    )
    assert reviewed.status_code == 200, reviewed.text

    manager_headers = _auth_headers(client, "frontend.sap.manager@example.com")
    manager_queue_before_policy = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=manager_headers,
    )
    assert manager_queue_before_policy.status_code == 200, manager_queue_before_policy.text
    assert manager_queue_before_policy.json() == []

    reviewed_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=accountant_headers,
    )
    assert reviewed_detail.status_code == 200, reviewed_detail.text
    assert reviewed_detail.json()["availableActions"] == ["prepare_sap_policy"]

    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/sap-policy/prepare/me",
        headers=accountant_headers,
        json={"reference": "SAP-FRONTEND-ORDER"},
    )
    assert sap_policy.status_code == 200, sap_policy.text

    accountant_detail_after_policy = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=accountant_headers,
    )
    assert accountant_detail_after_policy.status_code == 200, accountant_detail_after_policy.text
    assert accountant_detail_after_policy.json()["availableActions"] == [
        "start_accounting_manager_review"
    ]

    manager_queue_after_policy = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=manager_headers,
    )
    assert manager_queue_after_policy.status_code == 200, manager_queue_after_policy.text
    assert manager_queue_after_policy.json() == []

    manager_cannot_start_self_review = _transition(
        client,
        base_records["request_id"],
        "accounting_manager_review",
        manager_user_id,
    )
    assert manager_cannot_start_self_review.status_code == 409

    sent_to_manager = _transition(
        client,
        base_records["request_id"],
        "accounting_manager_review",
        accountant_user_id,
    )
    assert sent_to_manager.status_code == 200, sent_to_manager.text

    accountant_queue_after_send = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=accountant_headers,
    )
    assert accountant_queue_after_send.status_code == 200, accountant_queue_after_send.text
    assert accountant_queue_after_send.json() == []

    manager_queue_after_send = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=manager_headers,
    )
    assert manager_queue_after_send.status_code == 200, manager_queue_after_send.text
    assert manager_queue_after_send.json()[0]["backendStatus"] == "accounting_manager_review"
    assert manager_queue_after_send.json()[0]["availableActions"] == [
        "approve_accounting_manager",
        "return_to_accounting",
        "reject_request",
    ]


def test_frontend_historico_lists_paid_requests(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    admin_user_id = _create_user(client, "admin", "frontend.historico.admin@example.com")
    assert _transition(client, base_records["request_id"], "submitted", admin_user_id).status_code == 200
    assert (
        _transition(
            client,
            base_records["request_id"],
            "under_accounting_review",
            admin_user_id,
        ).status_code
        == 200
    )
    assert (
        _transition(
            client,
            base_records["request_id"],
            "accounting_reviewed",
            admin_user_id,
        ).status_code
        == 200
    )

    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/sap-policy/prepare",
        json={
            "actor_user_id": admin_user_id,
            "reference": "SAP-HISTORICO-001",
            "note": "Preparado para historico.",
        },
    )
    assert sap_policy.status_code == 200, sap_policy.text

    for target_status in [
        "accounting_manager_review",
        "accounting_manager_approved",
        "treasury_review",
        "direction_approved",
        "approved_for_payment",
    ]:
        response = _transition(client, base_records["request_id"], target_status, admin_user_id)
        assert response.status_code == 200, response.text

    headers = _auth_headers(client, "frontend.historico.admin@example.com")
    payment = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/payments/me",
        headers=headers,
        json={"reference": "PAGO-HISTORICO-001", "note": "Pago para historico."},
    )
    assert payment.status_code == 201, payment.text

    historico = client.get("/api/v1/frontend/historico/me", headers=headers)
    assert historico.status_code == 200, historico.text
    assert [item["backendId"] for item in historico.json()] == [base_records["request_id"]]
    assert historico.json()[0]["status"] == "Pagada"
    assert historico.json()[0]["backendStatus"] == "paid"


def test_frontend_historico_lists_rejected_requests(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    admin_user_id = _create_user(client, "admin", "frontend.historico.rejected.admin@example.com")
    assert _transition(client, base_records["request_id"], "submitted", admin_user_id).status_code == 200
    assert (
        _transition(
            client,
            base_records["request_id"],
            "under_accounting_review",
            admin_user_id,
        ).status_code
        == 200
    )

    removed = client.post(
        f"/api/v1/expenses/{expense['id']}/remove",
        json={
            "actor_user_id": admin_user_id,
            "reason": "No corresponde al reembolso",
            "adjust_reported_total": True,
        },
    )
    assert removed.status_code == 200, removed.text

    headers = _auth_headers(client, "frontend.historico.rejected.admin@example.com")
    historico = client.get("/api/v1/frontend/historico/me", headers=headers)
    assert historico.status_code == 200, historico.text
    assert [item["backendId"] for item in historico.json()] == [base_records["request_id"]]
    assert historico.json()[0]["status"] == "Rechazada"
    assert historico.json()[0]["backendStatus"] == "rejected"


def test_frontend_detail_keeps_removed_expenses_out_of_total(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    active_expense = create_expense(
        client,
        base_records,
        amount="1000.00",
        spent_on="2026-08-07",
    )
    removed_expense = create_expense(
        client,
        base_records,
        amount="500.00",
        spent_on="2026-08-08",
    )
    _attach_valid_cfdi(
        client,
        active_expense["id"],
        "1000.00",
        uuid="33333333-3333-4333-8333-333333333333",
    )
    _attach_valid_cfdi(
        client,
        removed_expense["id"],
        "500.00",
        uuid="44444444-4444-4444-8444-444444444444",
    )

    admin_user_id = _create_user(client, "admin", "frontend.removed.admin@example.com")
    submitted = _transition(client, base_records["request_id"], "submitted", admin_user_id)
    assert submitted.status_code == 200, submitted.text
    review = _transition(
        client,
        base_records["request_id"],
        "under_accounting_review",
        admin_user_id,
    )
    assert review.status_code == 200, review.text

    removal = client.post(
        f"/api/v1/expenses/{removed_expense['id']}/remove",
        json={
            "actor_user_id": admin_user_id,
            "reason": "No corresponde al reembolso",
            "adjust_reported_total": True,
        },
    )
    assert removal.status_code == 200, removal.text
    assert removal.json()["status"] == "removed"

    headers = _auth_headers(client, "frontend.removed.admin@example.com")
    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["montoTotal"] == 1000.0
    assert body["expenseCount"] == 1
    assert len(body["gastos"]) == 2

    removed_item = next(
        gasto for gasto in body["gastos"] if gasto["backendId"] == removed_expense["id"]
    )
    assert removed_item["status"] == "Eliminado"
    assert removed_item["backendStatus"] == "removed"
    assert removed_item["monto"] == 500.0


def test_accounting_queue_status_is_single_until_accountant_opens_request(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(
        client,
        expense["id"],
        "1500.00",
        uuid="55555555-5555-4555-8555-555555555555",
    )

    store_user_id = _create_user(client, "store", "frontend.single.store@example.com")
    accountant_user_id = _create_user(
        client,
        "accountant",
        "frontend.single.accountant@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["accounting_queue_status"] == "single"

    accountant_headers = _auth_headers(client, "frontend.single.accountant@example.com")
    accountant_queue = client.get("/api/v1/frontend/bandeja/me", headers=accountant_headers)
    assert accountant_queue.status_code == 200, accountant_queue.text
    assert accountant_queue.json()[0]["backendStatus"] == "submitted"
    assert accountant_queue.json()[0]["accountingQueueStatus"] == "single"

    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=accountant_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["backendStatus"] == "submitted"
    assert detail.json()["accountingQueueStatus"] == "taken"

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    assert "accounting_request_taken" in {event["action"] for event in audit_events.json()}


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret-password"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_user(client: TestClient, role: str, email: str) -> str:
    response = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "full_name": f"{role.title()} Demo",
            "role": role,
            "password": "secret-password",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _assign_user_to_store(client: TestClient, store_id: str, user_id: str, role: str) -> None:
    response = client.post(
        f"/api/v1/stores/{store_id}/users",
        json={"user_id": user_id, "role": role},
    )
    assert response.status_code == 201, response.text


def _transition(
    client: TestClient,
    request_id: str,
    target_status: str,
    actor_user_id: str,
):
    return client.post(
        f"/api/v1/reimbursement-requests/{request_id}/transition",
        json={
            "target_status": target_status,
            "actor_user_id": actor_user_id,
            "note": f"Move to {target_status}",
        },
    )


def _attach_valid_cfdi(
    client: TestClient,
    expense_id: str,
    amount: str,
    *,
    uuid: str = "22222222-2222-4222-8222-222222222222",
) -> None:
    cfdi = client.post(
        f"/api/v1/expenses/{expense_id}/cfdi/validate",
        files={
            "file": (
                "invoice.xml",
                _cfdi_xml(amount, uuid=uuid),
                "application/xml",
            )
        },
    )
    assert cfdi.status_code == 200, cfdi.text
    assert cfdi.json()["is_valid"] is True


def _cfdi_xml(amount: str, *, uuid: str = "22222222-2222-4222-8222-222222222222") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Fecha="2026-08-07T12:10:00"
    Total="{amount}"
    Moneda="MXN">
  <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Proveedor Demo"/>
  <cfdi:Receptor Rfc="BBB010101BBB" Nombre="Smolbox Demo"/>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital UUID="{uuid}"/>
  </cfdi:Complemento>
</cfdi:Comprobante>
""".encode()
