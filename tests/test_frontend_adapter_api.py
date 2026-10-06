from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from conftest import create_expense
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.endpoints import frontend, reimbursement_requests
from app.api.v1.endpoints.frontend import _frontend_tax_rate_for_expense
from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store_reimbursement_opening_cutoff import (
    StoreReimbursementOpeningCutoff,
)


def test_frontend_initial_tax_rules_assign_zero_percent() -> None:
    assert _frontend_tax_rate_for_expense(
        category="Agua",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("16.00"),
    ) == Decimal("0.00")
    assert _frontend_tax_rate_for_expense(
        category="Hospedaje",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("16.00"),
    ) == Decimal("0.00")
    assert _frontend_tax_rate_for_expense(
        category="Servicio de Agua",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("16.00"),
    ) == Decimal("16.00")
    assert _frontend_tax_rate_for_expense(
        category="No Deducibles",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("16.00"),
    ) == Decimal("0.00")
    assert _frontend_tax_rate_for_expense(
        category="No Deducible",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("16.00"),
    ) == Decimal("0.00")
    assert _frontend_tax_rate_for_expense(
        category="No Dedusible",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("16.00"),
    ) == Decimal("0.00")
    assert _frontend_tax_rate_for_expense(
        category="Pasajes y Taxis",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("16.00"),
    ) == Decimal("0.00")
    assert _frontend_tax_rate_for_expense(
        category="Otros",
        store_code="TIENDA-SIN-W6",
        requested_tax_rate=Decimal("0.00"),
    ) == Decimal("0.00")


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


def test_unassigned_accountant_can_see_and_start_global_accounting_queue(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    admin_user_id = _create_user(client, "admin", "frontend.global.admin@example.com")
    accountant_email = "frontend.global.accountant@example.com"
    _create_user(client, "accountant", accountant_email)

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        admin_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    accountant_headers = _auth_headers(client, accountant_email)
    frontend_queue = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=accountant_headers,
    )
    assert frontend_queue.status_code == 200, frontend_queue.text
    assert [item["backendId"] for item in frontend_queue.json()] == [
        base_records["request_id"]
    ]

    api_queue = client.get("/api/v1/work-queue/me", headers=accountant_headers)
    assert api_queue.status_code == 200, api_queue.text
    assert [item["id"] for item in api_queue.json()] == [base_records["request_id"]]

    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=accountant_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["availableActions"] == ["start_accounting_review"]

    review = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=accountant_headers,
        json={"target_status": "under_accounting_review", "note": "Inicio contabilidad"},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "under_accounting_review"


def test_unassigned_accounting_manager_can_see_global_post_accounting_queue(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    store_user_id = _create_user(client, "store", "frontend.global.manager.store@example.com")
    accountant_user_id = _create_user(
        client,
        "accountant",
        "frontend.global.manager.accountant@example.com",
    )
    manager_email = "frontend.global.manager@example.com"
    _create_user(client, "accounting_manager", manager_email)
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    reviewed = _transition(
        client,
        base_records["request_id"],
        "under_accounting_review",
        accountant_user_id,
    )
    assert reviewed.status_code == 200, reviewed.text
    reviewed = _transition(
        client,
        base_records["request_id"],
        "accounting_reviewed",
        accountant_user_id,
    )
    assert reviewed.status_code == 200, reviewed.text

    accountant_headers = _auth_headers(client, "frontend.global.manager.accountant@example.com")
    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/sap-policy/prepare/me",
        headers=accountant_headers,
        json={"reference": "SAP-GLOBAL-MANAGER"},
    )
    assert sap_policy.status_code == 200, sap_policy.text

    sent_to_manager = _transition(
        client,
        base_records["request_id"],
        "accounting_manager_review",
        accountant_user_id,
    )
    assert sent_to_manager.status_code == 200, sent_to_manager.text

    manager_headers = _auth_headers(client, manager_email)
    manager_queue = client.get("/api/v1/frontend/bandeja/me", headers=manager_headers)
    assert manager_queue.status_code == 200, manager_queue.text
    assert [item["backendId"] for item in manager_queue.json()] == [
        base_records["request_id"]
    ]

    manager_api_queue = client.get("/api/v1/work-queue/me", headers=manager_headers)
    assert manager_api_queue.status_code == 200, manager_api_queue.text
    assert [item["id"] for item in manager_api_queue.json()] == [
        base_records["request_id"]
    ]

    manager_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=manager_headers,
    )
    assert manager_detail.status_code == 200, manager_detail.text
    assert manager_detail.json()["availableActions"] == [
        "approve_accounting_manager",
        "return_to_accounting",
        "reject_request",
    ]


def test_frontend_can_create_request_and_lookup_by_folio(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
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
    _create_opening_cutoff(session_factory, store.json()["id"])
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

    with session_factory() as db:
        stored_request = db.get(
            ReimbursementRequest,
            UUID(created_body["backendId"]),
        )
        assert stored_request is not None
        assert stored_request.reimbursement_starts_on == date(2026, 8, 1)
        assert stored_request.reimbursement_ends_on == date(2026, 8, 7)

    detail = client.get(
        f"/api/v1/frontend/solicitudes/{created_body['folio']}/me",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["backendId"] == created_body["backendId"]


def test_request_calendar_dates_and_folios_use_mexico_city_time(
    monkeypatch,
) -> None:
    instant = datetime(2026, 10, 6, 4, 0, tzinfo=UTC)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz is not None else instant.replace(tzinfo=None)

    monkeypatch.setattr(frontend, "datetime", FixedDateTime)
    monkeypatch.setattr(reimbursement_requests, "datetime", FixedDateTime)
    db = type("FakeDb", (), {"scalars": lambda _self, _statement: []})()
    store = type("StoreStub", (), {"code": "T999"})()

    assert frontend._generate_request_folio(store, db) == "T999-051020261"
    assert reimbursement_requests._generate_request_folio(store, db) == "T999-051020261"
    assert frontend._parse_frontend_date(
        None,
        type(
            "PeriodStub",
            (),
            {
                "starts_on": date(2026, 10, 5),
                "ends_on": date(2026, 10, 6),
            },
        )(),
    ) == date(2026, 10, 5)


def test_frontend_delete_draft_expense_removes_it_before_submission(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "frontend.delete-draft@example.com",
            "full_name": "Frontend Delete Draft",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text
    store = client.post(
        "/api/v1/stores/",
        json={
            "code": "T997",
            "name": "Tienda Delete Draft",
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
    _create_opening_cutoff(session_factory, store.json()["id"])
    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Agosto Delete Draft",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-31",
        },
    )
    assert period.status_code == 201, period.text

    headers = _auth_headers(client, "frontend.delete-draft@example.com")
    created = client.post(
        "/api/v1/frontend/solicitudes/me",
        headers=headers,
        json={
            "tienda": "T997",
            "montoTotal": "300.00",
            "gastos": [
                {
                    "fecha": "08/08/2026",
                    "categoria": "Papelería",
                    "monto": "100.00",
                    "folio": "11111111-1111-4111-8111-111111111111",
                },
                {
                    "fecha": "07/08/2026",
                    "categoria": "Limpieza",
                    "monto": "200.00",
                    "folio": "22222222-2222-4222-8222-222222222222",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    with session_factory() as db:
        request = db.get(
            ReimbursementRequest,
            UUID(created_body["backendId"]),
        )
        assert request is not None
        assert request.reimbursement_ends_on == date(2026, 8, 8)

    deleted_expense = next(gasto for gasto in created_body["gastos"] if gasto["monto"] == 100.0)
    deleted_expense_id = deleted_expense["backendId"]
    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{created_body['backendId']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    created_messages = [
        event["message"]
        for event in audit_events.json()
        if event["action"] == "expense_created_from_frontend"
    ]
    assert set(created_messages) == {
        "Expense created for Gasto - Limpieza.",
        "Expense created for Gasto - Papelería.",
    }
    created_positions = {
        (
            event["event_payload"]["category"],
            event["event_payload"]["expense_sequence"],
            event["event_payload"]["expense_count"],
        )
        for event in audit_events.json()
        if event["action"] == "expense_created_from_frontend"
    }
    assert created_positions == {
        ("Papelería", "1", "2"),
        ("Limpieza", "2", "2"),
    }

    deleted = client.delete(
        (
            f"/api/v1/frontend/solicitudes/{created_body['backendId']}"
            f"/gastos/{deleted_expense_id}/me"
        ),
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text
    deleted_body = deleted.json()
    assert deleted_body["montoTotal"] == 200.0
    assert [gasto["monto"] for gasto in deleted_body["gastos"]] == [200.0]
    assert deleted_expense_id not in {gasto["backendId"] for gasto in deleted_body["gastos"]}

    with session_factory() as db:
        assert db.get(Expense, UUID(deleted_expense_id)) is None
        request = db.get(
            ReimbursementRequest,
            UUID(created_body["backendId"]),
        )
        assert request is not None
        assert request.reimbursement_ends_on == date(2026, 8, 7)

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{created_body['backendId']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    removed_event = next(
        event for event in audit_events.json() if event["action"] == "expense_removed_from_request"
    )
    assert removed_event["message"] == "Gasto eliminado por tienda: Gasto - Papelería."
    assert removed_event["event_payload"]["expense_id"] == deleted_expense_id
    assert removed_event["event_payload"]["expense_name"] == "Gasto - Papelería"
    remove_button_event = next(
        event
        for event in audit_events.json()
        if event["action"] == "button_selected"
        and event["event_payload"]["action_key"] == "remove_expense"
    )
    assert remove_button_event["message"] == "Botón seleccionado: Eliminar gasto."
    assert remove_button_event["event_payload"]["button_label"] == "Eliminar gasto"
    assert remove_button_event["event_payload"]["expense_id"] == deleted_expense_id


def test_frontend_clicks_are_registered_in_request_audit_log(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "frontend.click-audit@example.com",
            "full_name": "Frontend Click Audit",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text
    store = client.post(
        "/api/v1/stores/",
        json={
            "code": "T996",
            "name": "Tienda Click Audit",
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
    _create_opening_cutoff(session_factory, store.json()["id"])
    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Agosto Click Audit",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-31",
        },
    )
    assert period.status_code == 201, period.text

    headers = _auth_headers(client, "frontend.click-audit@example.com")
    created = client.post(
        "/api/v1/frontend/solicitudes/me",
        headers=headers,
        json={
            "tienda": "T996",
            "montoTotal": "125.00",
            "gastos": [
                {
                    "fecha": "07/08/2026",
                    "categoria": "Papelería",
                    "monto": "125.00",
                    "folio": "33333333-3333-4333-8333-333333333333",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    expense_id = created_body["gastos"][0]["backendId"]

    click = client.post(
        f"/api/v1/frontend/solicitudes/{created_body['backendId']}/clicks/me",
        headers=headers,
        json={
            "buttonLabel": "Ver Documento",
            "pagePath": "/detalle",
            "elementType": "button",
            "expenseId": expense_id,
        },
    )
    assert click.status_code == 201, click.text
    click_body = click.json()
    assert click_body["action"] == "ui_click"
    assert click_body["message"] == "Click registrado: Ver Documento."
    assert click_body["expense_id"] == expense_id
    assert click_body["event_payload"]["button_label"] == "Ver Documento"
    assert click_body["event_payload"]["page_path"] == "/detalle"

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{created_body['backendId']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    assert any(event["action"] == "ui_click" for event in audit_events.json())


def test_frontend_taxi_expense_routes_request_to_authorization(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
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
    _create_opening_cutoff(session_factory, base_records["store_id"])

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
                    "authorizationArea": "Supervisores",
                    "observaciones": "Traslado operativo",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    created_expense = created_body["gastos"][0]
    assert created_expense["requiresAuthorization"] is True
    assert created_expense["authorizationArea"] == "Supervisores"
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

    accountant_detail = client.get(
        f"/api/v1/frontend/solicitudes/{created_body['backendId']}/me",
        headers=accountant_headers,
    )
    assert accountant_detail.status_code == 403, accountant_detail.text


def test_frontend_taxi_expense_requires_authorization_area(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    store_user_id = _create_user(
        client,
        "store",
        "frontend.taxi.noarea.store@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _create_opening_cutoff(session_factory, base_records["store_id"])

    store_headers = _auth_headers(client, "frontend.taxi.noarea.store@example.com")
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
    assert created.status_code == 422, created.text
    assert created.json()["detail"]["code"] == "AUTHORIZATION_AREA_REQUIRED"


def test_frontend_fe006272_skips_authorization_and_routes_to_accounting(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    store = client.post(
        "/api/v1/stores/",
        json={"code": "FE006272", "name": "Tienda Sin Autorizacion"},
    )
    assert store.status_code == 201, store.text
    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Agosto FE006272",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-31",
        },
    )
    assert period.status_code == 201, period.text

    store_user_id = _create_user(client, "store", "frontend.noauth.store@example.com")
    authorizer_user_id = _create_user(
        client,
        "authorizer",
        "frontend.noauth.authorizer@example.com",
    )
    accountant_user_id = _create_user(
        client,
        "accountant",
        "frontend.noauth.accountant@example.com",
    )
    _assign_user_to_store(client, store.json()["id"], store_user_id, "store")
    _assign_user_to_store(client, store.json()["id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, store.json()["id"], accountant_user_id, "accountant")
    _create_opening_cutoff(session_factory, store.json()["id"])

    store_headers = _auth_headers(client, "frontend.noauth.store@example.com")
    created = client.post(
        "/api/v1/frontend/solicitudes/me",
        headers=store_headers,
        json={
            "tienda": "FE006272",
            "montoTotal": "1500.00",
            "gastos": [
                {
                    "fecha": "07/08/2026",
                    "categoria": "Pasajes y Taxis",
                    "monto": "1500.00",
                    "authorizationArea": "Supervisores",
                    "observaciones": "Traslado operativo sin autorizacion",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    created_body = created.json()
    created_expense = created_body["gastos"][0]
    assert created_expense["requiresAuthorization"] is False
    assert created_expense["autorizacion"] == ""

    _attach_valid_cfdi(
        client,
        created_expense["backendId"],
        "1500.00",
        uuid="77777777-7777-4777-8777-777777777777",
    )

    submitted = _transition(
        client,
        created_body["backendId"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    authorizer_headers = _auth_headers(client, "frontend.noauth.authorizer@example.com")
    authorizer_queue = client.get("/api/v1/frontend/bandeja/me", headers=authorizer_headers)
    assert authorizer_queue.status_code == 200, authorizer_queue.text
    assert authorizer_queue.json() == []

    accountant_headers = _auth_headers(client, "frontend.noauth.accountant@example.com")
    accountant_queue = client.get("/api/v1/frontend/bandeja/me", headers=accountant_headers)
    assert accountant_queue.status_code == 200, accountant_queue.text
    accountant_items = accountant_queue.json()
    assert [item["backendId"] for item in accountant_items] == [created_body["backendId"]]
    assert accountant_items[0]["availableActions"] == ["start_accounting_review"]


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
        action_key="start_accounting_review",
    )
    assert review.status_code == 200, review.text
    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    button_event = next(
        event for event in audit_events.json() if event["action"] == "button_selected"
    )
    assert button_event["message"] == "Botón seleccionado: Revisión contable."
    assert button_event["event_payload"]["action_key"] == "start_accounting_review"
    assert button_event["event_payload"]["button_label"] == "Revisión contable"

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
    store_user_id = _create_user(client, "store", "frontend.historico.store@example.com")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
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

    store_headers = _auth_headers(client, "frontend.historico.store@example.com")
    store_bandeja = client.get("/api/v1/frontend/bandeja/me", headers=store_headers)
    assert store_bandeja.status_code == 200, store_bandeja.text
    assert [item["backendId"] for item in store_bandeja.json()] == []

    store_historico = client.get("/api/v1/frontend/historico/me", headers=store_headers)
    assert store_historico.status_code == 200, store_historico.text
    assert [item["backendId"] for item in store_historico.json()] == [base_records["request_id"]]
    assert store_historico.json()[0]["status"] == "Pagada"
    assert store_historico.json()[0]["backendStatus"] == "paid"


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


def test_frontend_accounting_can_partition_expense(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(
        client,
        expense["id"],
        "1500.00",
        uuid="88888888-8888-4888-8888-888888888888",
    )
    admin_user_id = _create_user(client, "admin", "frontend.partition.admin@example.com")
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

    headers = _auth_headers(client, "frontend.partition.admin@example.com")
    partitioned = client.post(
        (
            f"/api/v1/frontend/solicitudes/{base_records['request_id']}"
            f"/gastos/{expense['id']}/particiones/me"
        ),
        headers=headers,
        json={
            "particiones": [
                {"categoria": "Papelería", "monto": "1000.00", "impuesto": "16.00"},
                {"categoria": "Agua", "monto": "500.00", "impuesto": "0.00"},
            ],
        },
    )
    assert partitioned.status_code == 200, partitioned.text
    body = partitioned.json()
    assert body["montoTotal"] == 1500.0
    assert body["expenseCount"] == 2

    parent = next(gasto for gasto in body["gastos"] if gasto["backendId"] == expense["id"])
    children = [gasto for gasto in body["gastos"] if gasto["idOriginal"] == expense["id"]]
    assert parent["inactivo"] is True
    assert parent["esParticionado"] is True
    assert len(children) == 2
    assert {child["tipo"] for child in children} == {"Papelería", "Agua"}
    assert {child["monto"] for child in children} == {1000.0, 500.0}
    assert all(child["esHijoParticion"] is True for child in children)
    assert all(child["folioFiscal"] == "88888888-8888-4888-8888-888888888888" for child in children)

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    created_event = next(
        event for event in audit_events.json() if event["action"] == "expense_partitioned"
    )
    assert "Partición creada sobre Gasto - Agua" in created_event["message"]
    assert "1/2: Categoría - Papelería, Monto - $1,000.00, Impuesto - 16%." in created_event["message"]
    assert "2/2: Categoría - Agua, Monto - $500.00, Impuesto - 0%." in created_event["message"]

    updated = client.post(
        (
            f"/api/v1/frontend/solicitudes/{base_records['request_id']}"
            f"/gastos/{expense['id']}/particiones/me"
        ),
        headers=headers,
        json={
            "particiones": [
                {"categoria": "Servicio de Agua", "monto": "900.00", "impuesto": "0.00"},
                {"categoria": "Papelería", "monto": "600.00", "impuesto": "16.00"},
            ],
        },
    )
    assert updated.status_code == 200, updated.text

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    updated_event = next(
        event for event in audit_events.json() if event["action"] == "expense_partition_updated"
    )
    assert "Partición editada sobre Gasto - Agua" in updated_event["message"]
    assert "1/2 cambió: categoría de Papelería a Servicio de Agua" in updated_event["message"]
    assert "monto de $1,000.00 a $900.00" in updated_event["message"]
    assert "impuesto de 16% a 0%" in updated_event["message"]


def test_frontend_accounting_can_cancel_expense_partition(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(
        client,
        expense["id"],
        "1500.00",
        uuid="99999999-9999-4999-8999-999999999999",
    )
    admin_user_id = _create_user(client, "admin", "frontend.partition.cancel.admin@example.com")
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

    headers = _auth_headers(client, "frontend.partition.cancel.admin@example.com")
    partitioned = client.post(
        (
            f"/api/v1/frontend/solicitudes/{base_records['request_id']}"
            f"/gastos/{expense['id']}/particiones/me"
        ),
        headers=headers,
        json={
            "particiones": [
                {"categoria": "Papelería", "monto": "1000.00", "impuesto": "16.00"},
                {"categoria": "Agua", "monto": "500.00", "impuesto": "0.00"},
            ],
        },
    )
    assert partitioned.status_code == 200, partitioned.text

    cancelled = client.delete(
        (
            f"/api/v1/frontend/solicitudes/{base_records['request_id']}"
            f"/gastos/{expense['id']}/particiones/me"
        ),
        headers=headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["montoTotal"] == 1500.0
    assert body["expenseCount"] == 1

    parent = next(gasto for gasto in body["gastos"] if gasto["backendId"] == expense["id"])
    children = [gasto for gasto in body["gastos"] if gasto["idOriginal"] == expense["id"]]
    assert parent["inactivo"] is False
    assert parent["esParticionado"] is False
    assert children == []

    repartitioned = client.post(
        (
            f"/api/v1/frontend/solicitudes/{base_records['request_id']}"
            f"/gastos/{expense['id']}/particiones/me"
        ),
        headers=headers,
        json={
            "particiones": [
                {"categoria": "Papelería", "monto": "900.00", "impuesto": "16.00"},
                {"categoria": "Agua", "monto": "600.00", "impuesto": "0.00"},
            ],
        },
    )
    assert repartitioned.status_code == 200, repartitioned.text
    repartitioned_body = repartitioned.json()
    active_children = [
        gasto
        for gasto in repartitioned_body["gastos"]
        if gasto["idOriginal"] == expense["id"]
    ]
    assert len(active_children) == 2
    assert {child["monto"] for child in active_children} == {900.0, 600.0}

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    cancelled_event = next(
        event for event in audit_events.json() if event["action"] == "expense_partition_cancelled"
    )
    assert "Partición anulada sobre Gasto - Agua" in cancelled_event["message"]
    assert "1/2: Categoría - Papelería, Monto - $1,000.00, Impuesto - 16%." in cancelled_event["message"]
    assert "2/2: Categoría - Agua, Monto - $500.00, Impuesto - 0%." in cancelled_event["message"]


def test_frontend_review_tax_change_uses_default_previous_tax_rate(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(
        client,
        base_records,
        amount="500.00",
        spent_on="2026-08-07",
        category="Papelería",
    )
    _attach_valid_cfdi(
        client,
        expense["id"],
        "500.00",
        uuid="10101010-1010-4010-8010-101010101010",
    )
    admin_user_id = _create_user(client, "admin", "frontend.tax.default.admin@example.com")
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

    headers = _auth_headers(client, "frontend.tax.default.admin@example.com")
    updated = client.patch(
        f"/api/v1/expenses/{expense['id']}/review/me",
        headers=headers,
        json={"cfdi_tax_rate": "0.00"},
    )
    assert updated.status_code == 200, updated.text

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    review_event = next(
        event for event in audit_events.json() if event["action"] == "expense_review_updated"
    )
    assert review_event["message"] == "Cambio de impuesto de 16% a 0%."


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
    second_accountant_user_id = _create_user(
        client,
        "accountant",
        "frontend.single.second.accountant@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")
    _assign_user_to_store(
        client,
        base_records["store_id"],
        second_accountant_user_id,
        "accountant",
    )

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

    second_accountant_headers = _auth_headers(
        client,
        "frontend.single.second.accountant@example.com",
    )
    second_accountant_queue = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=second_accountant_headers,
    )
    assert second_accountant_queue.status_code == 200, second_accountant_queue.text
    assert second_accountant_queue.json()[0]["accountingQueueStatus"] == "taken_other"

    second_accountant_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=second_accountant_headers,
    )
    assert second_accountant_detail.status_code == 200, second_accountant_detail.text
    assert second_accountant_detail.json()["accountingQueueStatus"] == "taken_other"
    assert "start_accounting_review" in second_accountant_detail.json()["availableActions"]

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    assert "accounting_request_taken" in {event["action"] for event in audit_events.json()}


def test_admin_opening_submitted_request_does_not_mark_accounting_queue_taken(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00", spent_on="2026-08-07")
    _attach_valid_cfdi(
        client,
        expense["id"],
        "1500.00",
        uuid="77777777-7777-4777-8777-777777777777",
    )

    admin_user_id = _create_user(client, "admin", "frontend.admin.single@example.com")
    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        admin_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["accounting_queue_status"] == "single"

    admin_headers = _auth_headers(client, "frontend.admin.single@example.com")
    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=admin_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["accountingQueueStatus"] == "single"

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200, audit_events.text
    assert "accounting_request_taken" not in {
        event["action"] for event in audit_events.json()
    }


def test_frontend_add_rejects_expense_before_previous_close(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    user = client.post(
        "/api/v1/users/",
        json={
            "email": "frontend.stale-expense@example.com",
            "full_name": "Frontend Stale Expense",
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

    response = client.post(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/gastos/me",
        headers=_auth_headers(client, "frontend.stale-expense@example.com"),
        json={
            "fecha": "30/07/2026",
            "categoria": "Papelería",
            "monto": "50.00",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "EXPENSE_OUTSIDE_PERIOD",
        "message": "El gasto está fuera de periodo.",
    }
    assert "2026" not in response.text


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


def _create_opening_cutoff(
    session_factory: sessionmaker[Session],
    store_id: str,
) -> None:
    with session_factory() as db:
        cutoff = db.scalar(
            select(StoreReimbursementOpeningCutoff).where(
                StoreReimbursementOpeningCutoff.store_id == UUID(store_id)
            )
        )
        if cutoff is None:
            cutoff = StoreReimbursementOpeningCutoff(
                store_id=UUID(store_id),
                starts_on=date(2026, 7, 1),
                ends_on=date(2026, 7, 31),
                reimbursed_amount=Decimal("0.00"),
                notes="Corte inicial de prueba",
            )
            db.add(cutoff)
        else:
            cutoff.starts_on = date(2026, 7, 1)
            cutoff.ends_on = date(2026, 7, 31)
            cutoff.reimbursed_amount = Decimal("0.00")
            cutoff.notes = "Corte inicial de prueba"
        db.commit()


def _transition(
    client: TestClient,
    request_id: str,
    target_status: str,
    actor_user_id: str,
    action_key: str | None = None,
):
    payload = {
        "target_status": target_status,
        "actor_user_id": actor_user_id,
        "note": f"Move to {target_status}",
    }
    if action_key:
        payload["action_key"] = action_key

    return client.post(
        f"/api/v1/reimbursement-requests/{request_id}/transition",
        json=payload,
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


def test_manager_productivity_counts_each_action_once_per_request_and_user(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    manager_id = _create_user(client, "accounting_manager", "prod.manager.one@example.com")
    other_manager_id = _create_user(client, "accounting_manager", "prod.manager.two@example.com")
    treasury_id = _create_user(client, "treasury", "prod.manager.treasury@example.com")
    _create_user(client, "director", "prod.manager.director@example.com")
    request_id = UUID(base_records["request_id"])

    _add_audit_event(
        session_factory, request_id, manager_id,
        "request_status_changed", "accounting_manager_approved",
        datetime(2026, 8, 10, 15, 0, tzinfo=UTC),
    )
    _add_audit_event(
        session_factory, request_id, manager_id,
        "request_status_changed", "accounting_manager_approved",
        datetime(2026, 8, 12, 15, 0, tzinfo=UTC),
    )
    _add_audit_event(
        session_factory, request_id, manager_id,
        "request_status_changed", "accounting_manager_approved",
        datetime(2026, 9, 2, 15, 0, tzinfo=UTC),
    )
    _add_audit_event(
        session_factory, request_id, manager_id,
        "payment_recorded", "paid",
        datetime(2026, 8, 13, 15, 0, tzinfo=UTC),
    )
    _add_audit_event(
        session_factory, request_id, other_manager_id,
        "request_status_changed", "accounting_manager_approved",
        datetime(2026, 8, 11, 15, 0, tzinfo=UTC),
    )
    _add_audit_event(
        session_factory, request_id, treasury_id,
        "request_status_changed", "accounting_manager_approved",
        datetime(2026, 8, 11, 16, 0, tzinfo=UTC),
    )

    headers = _auth_headers(client, "prod.manager.director@example.com")
    response = client.get(
        "/api/v1/frontend/gerencia/productividad/gerentes/me",
        params={"week_start": "2026-08-10", "month": 8, "year": 2026},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weekStartsOn"] == "2026-08-10"
    assert [action["key"] for action in body["actions"]] == ["send_to_treasury", "confirm_payment"]
    assert len(body["rows"]) == 4
    rows = {(row["userId"], row["actionKey"]): row for row in body["rows"]}
    assert rows[(manager_id, "send_to_treasury")]["values"] == {
        "Lu": 1, "Ma": 0, "Mi": 0, "Ju": 0, "Vi": 0,
    }
    assert rows[(manager_id, "confirm_payment")]["values"]["Ju"] == 1
    assert rows[(other_manager_id, "send_to_treasury")]["values"]["Ma"] == 1
    assert rows[(other_manager_id, "confirm_payment")]["total"] == 0
    assert body["totalsByAction"]["send_to_treasury"]["Lu"] == 1
    assert body["grandTotal"] == 3
    monthly = {(row["userId"], row["actionKey"]): row["total"] for row in body["monthlyRows"]}
    assert monthly[(manager_id, "send_to_treasury")] == 1
    assert monthly[(manager_id, "confirm_payment")] == 1
    assert body["monthlyGrandTotal"] == 3

    september = client.get(
        "/api/v1/frontend/gerencia/productividad/gerentes/me",
        params={"week_start": "2026-08-31", "month": 9, "year": 2026},
        headers=headers,
    )
    assert september.status_code == 200, september.text
    assert september.json()["monthlyGrandTotal"] == 0
    assert september.json()["grandTotal"] == 0


def test_treasury_productivity_counts_payment_approvals_by_treasury_users(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    treasury_id = _create_user(client, "treasury", "prod.treasury@example.com")
    director_id = _create_user(client, "director", "prod.treasury.director@example.com")
    request_id = UUID(base_records["request_id"])

    _add_audit_event(
        session_factory, request_id, treasury_id,
        "request_status_changed", "direction_approved",
        datetime(2026, 8, 12, 15, 0, tzinfo=UTC),
    )
    _add_audit_event(
        session_factory, request_id, director_id,
        "request_status_changed", "direction_approved",
        datetime(2026, 8, 12, 16, 0, tzinfo=UTC),
    )

    headers = _auth_headers(client, "prod.treasury.director@example.com")
    response = client.get(
        "/api/v1/frontend/gerencia/productividad/tesoreros/me",
        params={"week_start": "2026-08-10", "month": 8, "year": 2026},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [(row["userId"], row["actionKey"]) for row in body["rows"]] == [
        (treasury_id, "approve_payment")
    ]
    assert body["rows"][0]["values"]["Mi"] == 1
    assert body["grandTotal"] == 1
    assert body["monthlyGrandTotal"] == 1


def test_role_productivity_dashboards_are_limited_to_direction_and_admin(
    client: TestClient,
) -> None:
    _create_user(client, "accountant", "prod.forbidden.accountant@example.com")
    _create_user(client, "accounting_manager", "prod.forbidden.manager@example.com")
    _create_user(client, "admin", "prod.forbidden.admin@example.com")

    for path in ("gerentes", "tesoreros"):
        url = f"/api/v1/frontend/gerencia/productividad/{path}/me"
        for email in (
            "prod.forbidden.accountant@example.com",
            "prod.forbidden.manager@example.com",
        ):
            forbidden = client.get(url, headers=_auth_headers(client, email))
            assert forbidden.status_code == 403, forbidden.text
        allowed = client.get(url, headers=_auth_headers(client, "prod.forbidden.admin@example.com"))
        assert allowed.status_code == 200, allowed.text


def _add_audit_event(
    session_factory: sessionmaker[Session],
    request_id: UUID,
    actor_user_id: str,
    action: str,
    to_status: str,
    created_at: datetime,
) -> None:
    with session_factory() as db:
        db.add(
            AuditLog(
                reimbursement_request_id=request_id,
                actor_user_id=UUID(actor_user_id),
                actor_type=AuditActorType.user,
                action=action,
                to_status=to_status,
                created_at=created_at,
            )
        )
        db.commit()
