from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select
from test_cfdi_api import _cfdi_xml
from test_textract_ocr import _scanned_pdf

from app.models.audit_log import AuditLog
from app.models.expense import Expense
from app.models.historical_request import HistoricalAttachment
from app.models.payment import Payment
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store import StoreUserAssignment
from app.models.user import UserRole
from app.services.textract_ocr import TextractOcrResult, TextractOcrService

ROOT = "/api/v1/frontend/extemporaneos"


def user(client, role, suffix=""):
    email = f"{role}{suffix}@historical.test"
    result = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "password": "secret-password",
            "full_name": role,
            "role": role,
        },
    )
    assert result.status_code == 201, result.text
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-password"})
    assert token.status_code == 200, token.text
    return result.json()["id"], {"Authorization": f"Bearer {token.json()['access_token']}"}


@pytest.fixture
def scenario(client, base_records, session_factory):
    accountant, headers = user(client, "accountant")
    admin, admin_headers = user(client, "admin")
    store_user, store_headers = user(client, "store")
    with session_factory() as db:
        db.add(
            StoreUserAssignment(
                store_id=UUID(base_records["store_id"]),
                user_id=UUID(store_user),
                role=UserRole.store,
            )
        )
        db.commit()
    return {
        **base_records,
        "actor": accountant,
        "headers": headers,
        "admin": admin,
        "admin_headers": admin_headers,
        "store_user": store_user,
        "store_headers": store_headers,
    }


def draft(client, scenario, headers=None):
    result = client.post(
        f"{ROOT}/stores/{scenario['store_id']}/draft/me", headers=headers or scenario["headers"]
    )
    assert result.status_code == 200, result.text
    return result.json()


def expense(
    client,
    scenario,
    request_id,
    *,
    document_type="vale",
    amount="20.00",
    spent_on="2026-01-15",
    client_id=None,
    uuid=None,
):
    payload = {
        "clientId": client_id or str(uuid4()),
        "documentType": document_type,
        "categoria": "Pasajes y Taxis",
        "monto": amount,
        "fecha": spent_on,
        "observaciones": "Nota inicial pública",
        "cfdiUuid": uuid,
    }
    result = client.post(
        f"{ROOT}/{request_id}/expenses/me", headers=scenario["headers"], json=payload
    )
    assert result.status_code == 201, result.text
    return result.json(), payload


def document(client, scenario, expense_id, monkeypatch, *, xml=False):
    if xml:
        content = _cfdi_xml("12345678-ABCD-1234-ABCD-1234567890AB")
        filename, content_type = "factura.xml", "application/xml"
    else:
        content = _scanned_pdf()
        filename, content_type = "vale.pdf", "application/pdf"
        monkeypatch.setattr(TextractOcrService, "is_enabled", property(lambda self: True))
        monkeypatch.setattr(
            TextractOcrService,
            "extract_expense",
            lambda *args, **kwargs: TextractOcrResult(
                raw_text="COMERCIAL IAC\nCIA090819PW4\nTotal $20.00\nFecha 15/01/2026",
                extracted_total=Decimal("20.00"),
                extracted_date=datetime.fromisoformat("2026-01-15").date(),
                extracted_supplier="Proveedor",
                suggested_cfdi_uuid=None,
                confidence=Decimal(99),
                raw_response=None,
            ),
        )
    result = client.post(
        f"{ROOT}/expenses/{expense_id}/attachments/me",
        headers=scenario["headers"],
        files={"file": (filename, content, content_type)},
    )
    assert result.status_code == 201, result.text
    return result.json(), content


def register(client, scenario, request):
    result = client.post(
        f"{ROOT}/{request['backendId']}/register/me",
        headers=scenario["headers"],
        json={"expectedExpenseIds": [item["backendId"] for item in request["gastos"]]},
    )
    assert result.status_code == 200, result.text
    return result.json()


def snapshot(db, scenario):
    request = db.get(ReimbursementRequest, UUID(scenario["request_id"]))
    return {
        "request": {
            column.name: getattr(request, column.name) for column in request.__table__.columns
        },
        "expenses": db.scalar(select(func.count()).select_from(Expense)),
        "payments": db.scalar(select(func.count()).select_from(Payment)),
        "requests": db.scalar(select(func.count()).select_from(ReimbursementRequest)),
    }


@pytest.mark.parametrize("expire_on_commit", [False, True])
def test_end_to_end_paid_archive_is_persistent_isolated_and_idempotent(
    client,
    scenario,
    session_factory,
    monkeypatch,
    expire_on_commit,
):
    session_factory.configure(expire_on_commit=expire_on_commit)
    with session_factory() as db:
        before = snapshot(db, scenario)
    request = draft(client, scenario)
    assert draft(client, scenario)["backendId"] == request["backendId"]
    assert request["esExtemporaneo"] and not request["availableActions"]
    request, data = expense(client, scenario, request["backendId"])
    expense_id = request["gastos"][0]["backendId"]
    repeated = client.post(
        f"{ROOT}/{request['backendId']}/expenses/me", headers=scenario["headers"], json=data
    )
    assert len(repeated.json()["gastos"]) == 1
    changed = client.post(
        f"{ROOT}/{request['backendId']}/expenses/me",
        headers=scenario["headers"],
        json={**data, "monto": "21.00"},
    )
    assert changed.status_code == 409
    missing = client.post(
        f"{ROOT}/{request['backendId']}/register/me",
        headers=scenario["headers"],
        json={"expectedExpenseIds": [expense_id]},
    )
    assert missing.status_code == 409
    attachment, original = document(client, scenario, expense_id, monkeypatch)
    document(client, scenario, expense_id, monkeypatch)
    note = {"eventId": str(uuid4()), "note": "Comentario interno"}
    for _ in range(2):
        assert (
            client.post(
                f"{ROOT}/expenses/{expense_id}/observations/me",
                headers=scenario["headers"],
                json=note,
            ).status_code
            == 201
        )
    final = register(client, scenario, request)
    assert register(client, scenario, request)["folio"] == final["folio"]
    assert final["status"] == "Pagada" and final["backendStatus"] == "historical_paid"
    assert final["folio"].startswith("E-T001-") and final["elapsedDays"] is None
    assert final["montoTotal"] == 20 and final["gastos"][0]["requiresAuthorization"] is False
    history = client.get("/api/v1/frontend/historico/me", headers=scenario["headers"]).json()
    assert any(row["backendId"] == final["backendId"] and row["esExtemporaneo"] for row in history)
    assert not any(
        row["backendId"] == final["backendId"]
        for row in client.get("/api/v1/frontend/bandeja/me", headers=scenario["headers"]).json()
    )
    for path in (f"{ROOT}/{final['backendId']}/me", final["gastos"][0]["downloadUrl"]):
        assert client.get(path, headers=scenario["admin_headers"]).status_code == 200
    downloaded = client.get(
        f"{ROOT}/attachments/{attachment['id']}/download/me", headers=scenario["headers"]
    )
    assert downloaded.content == original
    zip_response = client.get(
        f"{ROOT}/{final['backendId']}/invoices.zip/me", headers=scenario["headers"]
    )
    with ZipFile(BytesIO(zip_response.content)) as archive:
        assert len(archive.namelist()) == 1 and archive.read(archive.namelist()[0]) == original
    assert (
        client.delete(f"{ROOT}/expenses/{expense_id}/me", headers=scenario["headers"]).status_code
        == 409
    )
    assert (
        client.post(
            f"{ROOT}/expenses/{expense_id}/observations/me", headers=scenario["headers"], json=note
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/reimbursement-requests/{final['backendId']}/transition/me",
            headers=scenario["headers"],
            json={"target_status": "paid"},
        ).status_code
        == 404
    )
    with session_factory() as db:
        assert snapshot(db, scenario) == before
        assert db.scalar(select(func.count()).select_from(HistoricalAttachment)) == 1
        logs = list(
            db.scalars(
                select(AuditLog).where(
                    AuditLog.event_payload["historical_request_id"].as_string()
                    == final["backendId"]
                )
            )
        )
        assert sum(log.action == "historical_request_registered" for log in logs) == 1
        assert sum(log.id == UUID(note["eventId"]) for log in logs) == 1
        assert all(log.reimbursement_request_id is None for log in logs)


def test_stores_roles_drafts_and_archived_document_access(
    client, scenario, session_factory, monkeypatch
):
    result = client.get(f"{ROOT}/stores/me", headers=scenario["headers"])
    assert [store["id"] for store in result.json()] == [scenario["store_id"]]
    assert client.get(f"{ROOT}/stores/me", headers=scenario["store_headers"]).status_code == 403
    # Existing draft permissions are not widened for Contabilidad.
    assert (
        client.post(
            f"/api/v1/frontend/solicitudes/tienda/{scenario['store_id']}/borrador/me",
            headers=scenario["headers"],
            json={},
        ).status_code
        == 403
    )
    request = draft(client, scenario)
    assert draft(client, scenario, scenario["admin_headers"])["backendId"] != request["backendId"]
    assert (
        client.get(
            f"{ROOT}/{request['backendId']}/me", headers=scenario["admin_headers"]
        ).status_code
        == 403
    )
    request, _ = expense(client, scenario, request["backendId"])
    attachment, _ = document(client, scenario, request["gastos"][0]["backendId"], monkeypatch)
    final = register(client, scenario, request)
    assert (
        client.get(f"{ROOT}/{final['backendId']}/me", headers=scenario["store_headers"]).status_code
        == 200
    )
    _, outsider = user(client, "store", "-other")
    for path in (
        f"{ROOT}/{final['backendId']}/me",
        f"{ROOT}/attachments/{attachment['id']}/download/me",
        f"{ROOT}/{final['backendId']}/invoices.zip/me",
    ):
        assert client.get(path, headers=outsider).status_code == 403
        assert client.get(path).status_code in {401, 403}
    with session_factory() as db:
        assignment = db.scalar(
            select(StoreUserAssignment).where(
                StoreUserAssignment.user_id == UUID(scenario["store_user"])
            )
        )
        assignment.is_active = False
        db.commit()
    assert client.get(f"{ROOT}/stores/me", headers=scenario["headers"]).json() == []


def test_dashboard_counts_only_registered_nonremoved_expenses_by_document_year(
    client,
    scenario,
    monkeypatch,
):
    request = draft(client, scenario)
    request, _ = expense(
        client, scenario, request["backendId"], amount="20.00", spent_on="2026-01-15"
    )
    request, _ = expense(
        client, scenario, request["backendId"], amount="30.00", spent_on="2025-01-15"
    )
    request, _ = expense(
        client, scenario, request["backendId"], amount="40.00", spent_on="2026-06-15"
    )
    removed = next(item["backendId"] for item in request["gastos"] if item["monto"] == 40)
    before = client.get(
        "/api/v1/frontend/tesoreria/dashboard/me", headers=scenario["headers"]
    ).json()
    productivity = client.get(
        "/api/v1/frontend/gerencia/productividad/me", headers=scenario["admin_headers"]
    ).json()
    request = client.delete(f"{ROOT}/expenses/{removed}/me", headers=scenario["headers"]).json()
    for item in request["gastos"]:
        document(client, scenario, item["backendId"], monkeypatch)
    register(client, scenario, request)
    after = client.get(
        "/api/v1/frontend/tesoreria/dashboard/me", headers=scenario["headers"]
    ).json()
    first = next(row for row in before["rows"] if row["storeId"] == scenario["store_id"])
    last = next(row for row in after["rows"] if row["storeId"] == scenario["store_id"])
    assert last["values"]["2026"] - first["values"]["2026"] == 20
    assert last["values"]["2025"] - first["values"]["2025"] == 30
    assert (
        client.get(
            "/api/v1/frontend/gerencia/productividad/me", headers=scenario["admin_headers"]
        ).json()
        == productivity
    )


def test_audit_capture_is_immediate_idempotent_and_observations_are_private(
    client,
    scenario,
    monkeypatch,
):
    request = draft(client, scenario)
    click = {
        "eventId": str(uuid4()),
        "action": "field_changed",
        "field": "category",
        "value": "Agua",
    }
    for _ in range(2):
        assert (
            client.post(
                f"{ROOT}/{request['backendId']}/events/me", headers=scenario["headers"], json=click
            ).status_code
            == 201
        )
    events = client.get(
        f"{ROOT}/{request['backendId']}/events/me", headers=scenario["headers"]
    ).json()
    assert sum(event["id"] == click["eventId"] for event in events) == 1
    assert any(event["message"] == "category: Agua" for event in events)
    day = datetime.now(UTC).date().isoformat()
    audit = client.get(
        f"/api/v1/frontend/audit-events/me?day={day}&utc_offset_minutes=0",
        headers=scenario["headers"],
    ).json()
    assert any(event["id"] == click["eventId"] for event in audit)
    request, _ = expense(client, scenario, request["backendId"])
    item = request["gastos"][0]
    note = {"eventId": str(uuid4()), "note": "Solo contabilidad"}
    client.post(
        f"{ROOT}/expenses/{item['backendId']}/observations/me",
        headers=scenario["headers"],
        json=note,
    )
    document(client, scenario, item["backendId"], monkeypatch)
    register(client, scenario, request)
    public = client.get(
        f"{ROOT}/{request['backendId']}/events/me", headers=scenario["store_headers"]
    ).json()
    assert not any(event["id"] == note["eventId"] for event in public)
    assert any(event["message"] == "Nota inicial pública" for event in public)


def test_xml_invoice_keeps_exact_rfc_validation_and_global_uuid_protection(
    client,
    scenario,
    monkeypatch,
):
    request = draft(client, scenario)
    uuid = "12345678-ABCD-1234-ABCD-1234567890AB"
    request, data = expense(
        client, scenario, request["backendId"], document_type="factura", uuid=uuid
    )
    expense_id = request["gastos"][0]["backendId"]
    normal_check = client.get(f"/api/v1/cfdi/uuid/{uuid}/availability").json()
    assert normal_check["is_available"] is False
    own_check = client.get(
        f"{ROOT}/uuid/{uuid}/availability/me?client_id={data['clientId']}",
        headers=scenario["headers"],
    ).json()
    assert own_check["is_available"] is True
    invalid = _cfdi_xml(uuid, receiver_attribute='Rfc="BBB010101BBX"')
    response = client.post(
        f"{ROOT}/expenses/{expense_id}/attachments/me",
        headers=scenario["headers"],
        files={"file": ("invoice.xml", invalid, "application/xml")},
    )
    assert response.status_code == 422
    document(client, scenario, expense_id, monkeypatch, xml=True)
    final = register(client, scenario, request)
    assert final["montoTotal"] == 20
    normal_duplicate = client.post(
        f"/api/v1/frontend/solicitudes/{scenario['request_id']}/gastos/me",
        headers=scenario["admin_headers"],
        json={"fecha": "2026-08-07", "categoria": "Papelería", "monto": "20", "folio": uuid},
    )
    assert normal_duplicate.status_code == 409
    # A different archive cannot use a fiscal UUID already included in a registered archive.
    next_draft = draft(client, scenario)
    response = client.post(
        f"{ROOT}/{next_draft['backendId']}/expenses/me",
        headers=scenario["headers"],
        json={**data, "clientId": str(uuid4())},
    )
    assert response.status_code == 409


def test_ocr_receiver_and_file_validation_are_not_bypassed(client, scenario, monkeypatch):
    request = draft(client, scenario)
    request, _ = expense(
        client, scenario, request["backendId"], document_type="factura", uuid=str(uuid4())
    )
    expense_id = request["gastos"][0]["backendId"]
    response = client.post(
        f"{ROOT}/expenses/{expense_id}/attachments/me",
        headers=scenario["headers"],
        files={"file": ("invoice.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 415
    monkeypatch.setattr(TextractOcrService, "is_enabled", property(lambda self: True))
    monkeypatch.setattr(
        TextractOcrService,
        "extract_expense",
        lambda *args, **kwargs: TextractOcrResult(
            raw_text="OTRO RECEPTOR\nABC010101AB1\nTotal 20.00",
            extracted_total=Decimal(20),
            extracted_date=None,
            extracted_supplier=None,
            suggested_cfdi_uuid=None,
            confidence=None,
            raw_response=None,
        ),
    )
    response = client.post(
        f"{ROOT}/expenses/{expense_id}/attachments/me",
        headers=scenario["headers"],
        files={"file": ("invoice.pdf", _scanned_pdf(), "application/pdf")},
    )
    assert response.status_code == 409
    assert "receptor" in response.text


def test_register_rejects_stale_expense_list_and_event_id_reuse(client, scenario):
    request = draft(client, scenario)
    first_id = request["backendId"]
    request, _ = expense(client, scenario, first_id)
    stale = client.post(
        f"{ROOT}/{first_id}/register/me",
        headers=scenario["headers"],
        json={"expectedExpenseIds": [str(uuid4())]},
    )
    assert stale.status_code == 409
    payload = {
        "eventId": str(uuid4()),
        "action": "field_changed",
        "field": "category",
        "value": "Agua",
    }
    assert (
        client.post(
            f"{ROOT}/{first_id}/events/me", headers=scenario["headers"], json=payload
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{ROOT}/{first_id}/events/me",
            headers=scenario["headers"],
            json={**payload, "value": "Otro"},
        ).status_code
        == 409
    )


def test_archive_needs_neither_open_period_nor_opening_cutoff(client, session_factory, monkeypatch):
    _, headers = user(client, "accountant")
    store_user, _ = user(client, "store")
    result = client.post("/api/v1/stores/", json={"code": "X001", "name": "Sin periodo"})
    store_id = result.json()["id"]
    with session_factory() as db:
        db.add(
            StoreUserAssignment(
                store_id=UUID(store_id), user_id=UUID(store_user), role=UserRole.store
            )
        )
        db.commit()
    sample = {"store_id": store_id, "headers": headers}
    request = draft(client, sample)
    request, _ = expense(client, sample, request["backendId"], spent_on="2001-01-01")
    document(client, sample, request["gastos"][0]["backendId"], monkeypatch)
    assert register(client, sample, request)["status"] == "Pagada"
