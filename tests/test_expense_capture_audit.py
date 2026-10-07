from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store_reimbursement_opening_cutoff import StoreReimbursementOpeningCutoff
from app.services.textract_ocr import (
    OCR_UNREADABLE_DOCUMENT_MESSAGE,
    TextractOcrError,
    TextractOcrResult,
    TextractOcrService,
)


def _user(client, store_id, *, email="capture@example.com", role="store"):
    user = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "full_name": "Usuario Captura",
            "role": role,
            "password": "secret-password",
        },
    )
    assert user.status_code == 201, user.text
    if store_id:
        assigned = client.post(
            f"/api/v1/stores/{store_id}/users",
            json={
                "user_id": user.json()["id"],
                "role": role,
            },
        )
        assert assigned.status_code == 201, assigned.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-password"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _start(client, headers, request_id=None):
    payload = {"captureId": str(uuid4()), "requestId": request_id}
    response = client.post("/api/v1/frontend/capturas/me", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _event(client, headers, capture_id, action, **details):
    return client.post(
        f"/api/v1/frontend/capturas/{capture_id}/eventos/me",
        headers=headers,
        json={
            "eventId": str(uuid4()),
            "action": action,
            **details,
        },
    )


def _list(client, headers, day=None, **params):
    return client.get(
        "/api/v1/frontend/audit-events/me",
        headers=headers,
        params={
            "day": day or datetime.now(UTC).date().isoformat(),
            "utc_offset_minutes": 0,
            **params,
        },
    )


def _expense(capture_id):
    return {
        "captureId": capture_id,
        "fecha": "07/08/2026",
        "categoria": "Papelería",
        "monto": "100.00",
        "folio": "11111111-2222-4333-8444-AAAAAAAAAAAA",
    }


def test_capture_records_immediately_without_creating_a_request_or_expense(
    client, base_records, session_factory
):
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    changed = _event(
        client,
        headers,
        capture["id"],
        "field_changed",
        field="category",
        previousValue="Papelería",
        value="Agua",
    )
    assert changed.status_code == 201, changed.text
    assert changed.json()["message"] == "Cambio de categoría de Papelería a Agua durante captura."
    events = _list(client, headers)
    assert events.status_code == 200, events.text
    row = next(row for row in events.json() if row["id"] == changed.json()["id"])
    assert row["reimbursement_request_id"] is None
    assert row["expense_id"] is None
    assert row["store_code"] == "T001"
    assert row["actor_name"] == "Usuario Captura"
    assert row["actor_role"] == "store"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(ReimbursementRequest)) == 1
        assert db.scalar(select(func.count()).select_from(Expense)) == 0


def test_capture_start_and_event_retries_keep_one_original_event(
    client, base_records, session_factory
):
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    repeated = client.post(
        "/api/v1/frontend/capturas/me", headers=headers, json={"captureId": capture["id"]}
    )
    assert repeated.json()["created_at"] == capture["created_at"]
    payload = {"eventId": str(uuid4()), "action": "click", "label": "Validar Gasto"}
    url = f"/api/v1/frontend/capturas/{capture['id']}/eventos/me"
    first = client.post(url, headers=headers, json=payload)
    second = client.post(url, headers=headers, json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    with session_factory() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.event_payload["capture_id"].as_string() == capture["id"])
            )
            == 2
        )


def test_cancelled_capture_remains_visible_and_cannot_be_added(
    client, base_records, session_factory
):
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    cancelled = _event(client, headers, capture["id"], "cancelled")
    assert cancelled.status_code == 201
    assert "sin añadir" in cancelled.json()["message"]
    assert cancelled.json()["id"] in {e["id"] for e in _list(client, headers).json()}
    assert _event(client, headers, capture["id"], "click", label="Añadir").status_code == 409
    added = client.post(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/gastos/me",
        headers=headers,
        json=_expense(capture["id"]),
    )
    assert added.status_code == 409, added.text
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Expense)) == 0


def test_add_links_all_existing_capture_events_without_changing_times(client, base_records):
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    changed = _event(
        client, headers, capture["id"], "field_changed", field="amount", value="100.00"
    ).json()
    added = client.post(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/gastos/me",
        headers=headers,
        json=_expense(capture["id"]),
    )
    assert added.status_code == 201, added.text
    expense_id = added.json()["gastos"][0]["backendId"]
    rows = {e["id"]: e for e in _list(client, headers).json()}
    for original in [capture, changed]:
        row = rows[original["id"]]
        assert row["created_at"] == original["created_at"]
        assert row["reimbursement_request_id"] == base_records["request_id"]
        assert row["expense_id"] == expense_id
        assert row["request_folio"] == added.json()["folio"]
    assert any(e["action"] == "expense_capture_added" for e in rows.values())


def test_first_expense_creates_request_and_links_preexisting_capture(
    client, base_records, session_factory
):
    headers = _user(client, base_records["store_id"])
    with session_factory() as db:
        cutoff = db.scalar(
            select(StoreReimbursementOpeningCutoff).where(
                StoreReimbursementOpeningCutoff.store_id == UUID(base_records["store_id"])
            )
        )
        cutoff.starts_on = date(2026, 7, 1)
        cutoff.ends_on = date(2026, 7, 31)
        db.commit()
    capture = _start(client, headers)
    created = client.post(
        "/api/v1/frontend/solicitudes/me",
        headers=headers,
        json={
            "tienda": "T001",
            "period_id": base_records["period_id"],
            "gastos": [_expense(capture["id"])],
        },
    )
    assert created.status_code == 201, created.text
    rows = _list(client, headers).json()
    row = next(row for row in rows if row["id"] == capture["id"])
    assert row["expense_id"] == created.json()["gastos"][0]["backendId"]
    assert row["reimbursement_request_id"] == created.json()["backendId"]


def test_capture_permissions_prevent_other_users_and_store_leaks(client, base_records):
    owner = _user(client, base_records["store_id"])
    capture = _start(client, owner)
    other_store = client.post("/api/v1/stores/", json={"code": "T002", "name": "Otra"}).json()
    other = _user(client, other_store["id"], email="other@example.com")
    assert _event(client, other, capture["id"], "click", label="Añadir").status_code == 404
    assert capture["id"] not in {e["id"] for e in _list(client, other).json()}
    wrong_request = client.post(
        "/api/v1/frontend/capturas/me",
        headers=other,
        json={
            "captureId": str(uuid4()),
            "requestId": base_records["request_id"],
        },
    )
    assert wrong_request.status_code == 403
    director = _user(client, None, email="director@example.com", role="director")
    assert capture["id"] in {e["id"] for e in _list(client, director).json()}


def test_capture_requires_authentication_and_rejects_forged_actor_data(client, base_records):
    assert (
        client.post("/api/v1/frontend/capturas/me", json={"captureId": str(uuid4())}).status_code
        == 401
    )
    assert _list(client, {}).status_code == 401
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    assert (
        _event(
            client, headers, capture["id"], "click", label="Añadir", actor_role="admin"
        ).status_code
        == 422
    )
    assert (
        _event(
            client, headers, capture["id"], "field_changed", field="password", value="secret"
        ).status_code
        == 422
    )


def test_audit_day_filter_uses_local_day_and_supports_pagination(
    client, base_records, session_factory
):
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    with session_factory() as db:
        db.get(AuditLog, UUID(capture["id"])).created_at = datetime(2026, 8, 7, 3, 0, tzinfo=UTC)
        db.commit()
    assert capture["id"] in {
        e["id"] for e in _list(client, headers, "2026-08-06", utc_offset_minutes=-360).json()
    }
    assert capture["id"] not in {
        e["id"] for e in _list(client, headers, "2026-08-07", utc_offset_minutes=-360).json()
    }
    first = _list(client, headers, "2026-08-06", utc_offset_minutes=-360, limit=1).json()
    next_page = _list(
        client, headers, "2026-08-06", utc_offset_minutes=-360, limit=1, offset=1
    ).json()
    assert len(first) == 1
    assert next_page == []


@pytest.mark.parametrize(
    "mode,expected_status", [("success", 200), ("partial", 200), ("error", 502), ("receiver", 409)]
)
def test_ocr_preview_records_server_outcome_before_add_and_preserves_alerts(
    client,
    base_records,
    session_factory,
    monkeypatch,
    test_settings,
    mode,
    expected_status,
):
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    test_settings.textract_enabled = True

    def extract(self, content, **kwargs):
        if mode == "error":
            raise TextractOcrError("AWS document could not be read")
        return TextractOcrResult(
            raw_text="Otra empresa" if mode == "receiver" else "COMERCIAL IAC CIA090819PW4",
            extracted_total=None if mode == "partial" else Decimal("100.00"),
            extracted_date=None if mode == "partial" else date(2026, 8, 7),
            extracted_supplier=None,
            suggested_cfdi_uuid=None,
            confidence=None,
            raw_response=None,
        )

    monkeypatch.setattr(TextractOcrService, "extract_expense", extract)
    response = client.post(
        "/api/v1/cfdi/ocr-preview",
        headers=headers,
        data={"capture_id": capture["id"]},
        files={"file": ("invoice.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert response.status_code == expected_status, response.text
    if mode == "error":
        assert response.json()["detail"]["message"] == OCR_UNREADABLE_DOCUMENT_MESSAGE
    elif mode == "receiver":
        assert response.json()["detail"]["code"] == "OCR_RECEIVER_MISMATCH"
    elif mode == "partial":
        assert response.json()["extracted_total"] is None
    events = [
        e
        for e in _list(client, headers).json()
        if (e["event_payload"] or {}).get("capture_id") == capture["id"]
    ]
    assert len(events) == 3
    actions = {e["action"] for e in events}
    assert "expense_capture_ocr_started" in actions
    assert (
        "expense_capture_ocr_completed" if expected_status == 200 else "expense_capture_ocr_failed"
    ) in actions
    assert all(e["expense_id"] is None for e in events)
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Expense)) == 0


def test_ocr_cannot_use_another_users_capture(client, base_records, monkeypatch, test_settings):
    headers = _user(client, base_records["store_id"])
    capture = _start(client, headers)
    other = _user(client, base_records["store_id"], email="other@example.com")
    calls = []
    monkeypatch.setattr(TextractOcrService, "extract_expense", lambda *a, **kw: calls.append(True))
    test_settings.textract_enabled = True
    for auth, expected in [({}, 401), (other, 404)]:
        response = client.post(
            "/api/v1/cfdi/ocr-preview",
            headers=auth,
            data={"capture_id": capture["id"]},
            files={"file": ("invoice.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
        )
        assert response.status_code == expected, response.text
    assert calls == []
