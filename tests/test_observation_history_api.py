from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from conftest import authenticated_audit_headers, create_expense

from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense, ExpenseStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.user import User
from app.services.expense_observations import can_add_expense_observation


def _actor(client, base_records, role, *, assigned=True):
    email = f"observations-{role}@example.com"
    created = client.post("/api/v1/users/", json={
        "email": email, "full_name": f"Observations {role}", "role": role, "password": "secret-password",
    })
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    if assigned:
        assigned_response = client.post(f"/api/v1/stores/{base_records['store_id']}/users", json={"user_id": user_id, "role": role})
        assert assigned_response.status_code == 201, assigned_response.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-password"})
    assert login.status_code == 200, login.text
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _note(db, records, expense_id, message, role="authorizer", *, action="expense_observation_added", created_at=None):
    db.add(AuditLog(
        reimbursement_request_id=UUID(records["request_id"]), expense_id=UUID(expense_id),
        actor_type=AuditActorType.system, action=action, message=message,
        event_payload={"actor_role": role}, created_at=created_at or datetime.now(UTC),
    ))


def _path(records):
    return f"/api/v1/reimbursement-requests/{records['request_id']}/audit-events"


def test_audit_reads_require_session(client, base_records):
    assert client.get(_path(base_records)).status_code == 401
    assert client.get(_path(base_records), params={"observations_only": True}).status_code == 401


def test_observation_pages_are_filtered_before_pagination(client, base_records, session_factory):
    expense = create_expense(client, base_records)
    headers = authenticated_audit_headers(client)
    with session_factory() as db:
        for index in range(225):
            _note(db, base_records, expense["id"], f"Note {index}", created_at=datetime.now(UTC) - timedelta(hours=1, seconds=index))
        for index in range(600):
            _note(db, base_records, expense["id"], f"Click {index}", action="ui_click")
        db.commit()
    params = {"observations_only": True, "limit": 200}
    first = client.get(_path(base_records), headers=headers, params=params)
    second = client.get(_path(base_records), headers=headers, params={**params, "offset": 200})
    assert first.status_code == second.status_code == 200
    assert len(first.json()) == 200
    assert len(second.json()) == 25
    assert len({row["id"] for row in first.json() + second.json()}) == 225
    assert all(row["message"].startswith("Note ") for row in first.json() + second.json())


@pytest.mark.parametrize("role", ["store", "authorizer", "accountant", "accounting_manager", "treasury", "director", "admin"])
def test_history_visibility_and_paid_read_access(client, base_records, session_factory, role):
    expense = create_expense(client, base_records)
    _, headers = _actor(client, base_records, role)
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.status = ReimbursementRequestStatus.paid
        _note(db, base_records, expense["id"], "Store public", "store")
        _note(db, base_records, expense["id"], "Supervisor public")
        _note(db, base_records, expense["id"], "Private accounting", "accountant")
        _note(db, base_records, expense["id"], "Public rejection", "accountant", action="expense_authorization_rejected")
        db.commit()
    for params in [{}, {"observations_only": True}]:
        response = client.get(_path(base_records), headers=headers, params=params)
        assert response.status_code == 200, response.text
        messages = {row["message"] for row in response.json()}
        assert {"Store public", "Supervisor public", "Public rejection"} <= messages
        assert ("Private accounting" in messages) == (role not in {"store", "authorizer"})
    with session_factory() as db:
        assert db.get(ReimbursementRequest, UUID(base_records["request_id"])).status == ReimbursementRequestStatus.paid
    if role == "store":
        daily = client.get("/api/v1/frontend/audit-events/me", headers=headers, params={"day": datetime.now(UTC).date().isoformat(), "utc_offset_minutes": 0})
        assert daily.status_code == 200
        assert all(row["message"] != "Private accounting" for row in daily.json())


def test_store_cannot_read_another_store_history(client, base_records):
    _, headers = _actor(client, base_records, "store", assigned=False)
    response = client.get(_path(base_records), headers=headers, params={"observations_only": True})
    assert response.status_code == 403


def test_legacy_actor_role_is_returned_without_exposing_private_notes(client, base_records, session_factory):
    expense = create_expense(client, base_records)
    _, headers = _actor(client, base_records, "store")
    supervisor_id, _ = _actor(client, base_records, "authorizer")
    accountant_id, _ = _actor(client, base_records, "accountant")
    with session_factory() as db:
        for actor_id, message, payload in [
            (supervisor_id, "Legacy public", {}),
            (accountant_id, "Legacy private", {}),
            (supervisor_id, "Previously private", {"actor_role": "accountant"}),
            (accountant_id, "Previously public", {"actor_role": "store"}),
        ]:
            db.add(AuditLog(
                reimbursement_request_id=UUID(base_records["request_id"]), expense_id=UUID(expense["id"]),
                actor_user_id=UUID(actor_id), actor_type=AuditActorType.user,
                action="expense_observation_added", message=message, event_payload=payload,
            ))
        db.commit()
    response = client.get(_path(base_records), headers=headers, params={"observations_only": True})
    assert response.status_code == 200
    assert {row["message"]: row["actor_role"] for row in response.json()} == {
        "Legacy public": "authorizer", "Previously public": "store",
    }


def test_area_authorizer_only_reads_its_expenses(client, base_records, session_factory):
    systems = create_expense(client, base_records)
    hr = create_expense(client, base_records)
    user_id, headers = _actor(client, base_records, "authorizer", assigned=False)
    admin = authenticated_audit_headers(client)
    assigned = client.post(f"/api/v1/authorization-areas/users/{user_id}", headers=admin, json={"areaName": "Sistemas"})
    assert assigned.status_code == 201
    systems_area_id = assigned.json()["authorization_area"]["id"]
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.status = ReimbursementRequestStatus.authorization_review
        for expense_id in [systems["id"], hr["id"]]:
            db.get(Expense, UUID(expense_id)).requires_authorization = True
        db.get(Expense, UUID(systems["id"])).authorization_area_id = UUID(systems_area_id)
        _note(db, base_records, systems["id"], "Systems note")
        _note(db, base_records, hr["id"], "Other area note")
        db.commit()
    response = client.get(_path(base_records), headers=headers, params={"observations_only": True})
    assert response.status_code == 200, response.text
    assert [row["message"] for row in response.json()] == ["Systems note"]


def test_initial_note_is_persisted_once_and_remains_public(client, base_records):
    _, headers = _actor(client, base_records, "store")
    created = client.post(f"/api/v1/frontend/solicitudes/{base_records['request_id']}/gastos/me", headers=headers, json={
        "fecha": "07/08/2026", "categoria": "Agua", "monto": "100.00", "observaciones": "Original store note",
    })
    assert created.status_code == 201, created.text
    history = client.get(_path(base_records), headers=headers, params={"observations_only": True})
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["message"] == "Original store note"
    assert history.json()[0]["event_payload"]["is_initial_observation"] is True


def test_imported_initial_note_is_not_added_twice(client, base_records):
    headers = authenticated_audit_headers(client)
    created = client.post(f"/api/v1/frontend/solicitudes/{base_records['request_id']}/gastos/me", headers=headers, json={
        "fecha": "07/08/2026", "categoria": "Agua", "monto": "100.00", "observaciones": "Original note",
        "observacionesHistorial": [{"texto": "Original note", "rol": "tienda", "autor": "TIENDA", "visibilidad": "PUBLIC"}],
    })
    assert created.status_code == 201, created.text
    history = client.get(_path(base_records), headers=headers, params={"observations_only": True})
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["event_payload"]["is_initial_observation"] is True


@pytest.mark.parametrize("request_status", ["draft", "correction_required"])
def test_store_can_comment_own_editable_request_without_changing_financial_data(client, base_records, session_factory, request_status):
    expense = create_expense(client, base_records)
    user_id, headers = _actor(client, base_records, "store")
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.status = ReimbursementRequestStatus(request_status)
        item = db.get(Expense, UUID(expense["id"]))
        item.description = "Original initial note"
        original_amount, original_date, original_tax = item.amount, item.spent_on, item.cfdi_tax_rate
        original_total = request.reported_total
        db.commit()
    detail = client.get(f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["gastos"][0]["canAddObservation"] is True
    assert datetime.fromisoformat(detail.json()["gastos"][0]["createdAt"]).tzinfo is not None
    for note in ["Store comment one", "Store comment two"]:
        response = client.post(f"/api/v1/expenses/{expense['id']}/observation/me", headers=headers, json={"note": note})
        assert response.status_code == 200, response.text
    history = client.get(_path(base_records), headers=headers, params={"observations_only": True}).json()
    assert {row["message"] for row in history} == {"Store comment one", "Store comment two"}
    assert all(row["actor_user_id"] == user_id and row["event_payload"]["actor_role"] == "store" for row in history)
    with session_factory() as db:
        item = db.get(Expense, UUID(expense["id"]))
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert item.description == "Original initial note"
        assert (item.amount, item.spent_on, item.cfdi_tax_rate) == (original_amount, original_date, original_tax)
        assert request.reported_total == original_total
        assert request.status.value == request_status


def test_observation_permissions_preserve_all_other_role_and_stage_rules(client, base_records, session_factory):
    expense = create_expense(client, base_records)
    actors = {role: _actor(client, base_records, role) for role in ["store", "authorizer", "accountant", "accounting_manager", "treasury", "director", "admin"]}
    expected = {
        "draft": {"store"}, "correction_required": {"store"},
        "submitted": {"authorizer", "accountant", "admin"},
        "authorization_review": {"authorizer", "admin"},
        "authorized": {"authorizer", "accountant", "admin"},
        "under_accounting_review": {"accountant", "admin"},
        "accounting_reviewed": {"accountant", "accounting_manager", "admin"},
        "accounting_approved": {"accountant", "accounting_manager", "treasury", "admin"},
        "accounting_manager_review": {"accounting_manager", "admin"},
        "accounting_manager_approved": {"accounting_manager", "treasury", "admin"},
        "treasury_review": {"treasury", "admin"},
        "direction_review": {"treasury", "director", "admin"},
        "direction_approved": {"accounting_manager", "treasury", "director", "admin"},
        "approved_for_payment": {"accounting_manager", "treasury", "director", "admin"},
    }
    for request_status in ReimbursementRequestStatus:
        with session_factory() as db:
            db.get(ReimbursementRequest, UUID(base_records["request_id"])).status = request_status
            db.commit()
        for role, (user_id, headers) in actors.items():
            allowed = role in expected.get(request_status.value, set())
            with session_factory() as db:
                item = db.get(Expense, UUID(expense["id"]))
                previous_note = item.review_note
                assert can_add_expense_observation(db, db.get(User, UUID(user_id)), item) is allowed, (role, request_status)
            note = f"{role} at {request_status.value}"
            response = client.post(f"/api/v1/expenses/{expense['id']}/observation/me", headers=headers, json={"note": note})
            assert response.status_code == (200 if allowed else 409), (role, request_status, response.text)
            with session_factory() as db:
                assert db.get(Expense, UUID(expense["id"])).review_note == (note if allowed else previous_note)
                assert db.get(ReimbursementRequest, UUID(base_records["request_id"])).status == request_status


def test_store_cannot_comment_other_store_or_use_legacy_actor_id_route(client, base_records):
    expense = create_expense(client, base_records)
    user_id, headers = _actor(client, base_records, "store", assigned=False)
    denied = client.post(f"/api/v1/expenses/{expense['id']}/observation/me", headers=headers, json={"note": "Not my store"})
    assert denied.status_code == 403, denied.text
    denied_legacy = client.post(f"/api/v1/expenses/{expense['id']}/observation", json={"note": "No session", "actor_user_id": user_id})
    assert denied_legacy.status_code == 409
    assert denied_legacy.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"
    assert client.post(f"/api/v1/expenses/{expense['id']}/observation/me", json={"note": "Anonymous"}).status_code == 401


@pytest.mark.parametrize("expense_status", ["removed", "rejected"])
def test_store_cannot_comment_excluded_expense(client, base_records, session_factory, expense_status):
    expense = create_expense(client, base_records)
    _, headers = _actor(client, base_records, "store")
    with session_factory() as db:
        db.get(Expense, UUID(expense["id"])).status = ExpenseStatus(expense_status)
        db.commit()
    detail = client.get(f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["gastos"][0]["canAddObservation"] is False
    response = client.post(f"/api/v1/expenses/{expense['id']}/observation/me", headers=headers, json={"note": "Excluded"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EXPENSE_EXCLUDED"


def test_partition_payload_has_real_creation_time_and_comments_keep_their_expense(client, base_records, session_factory):
    expense = create_expense(client, base_records, amount="100.00")
    admin = authenticated_audit_headers(client)
    _, store = _actor(client, base_records, "store")
    with session_factory() as db:
        db.get(ReimbursementRequest, UUID(base_records["request_id"])).status = ReimbursementRequestStatus.under_accounting_review
        db.commit()
    split = client.post(f"/api/v1/frontend/solicitudes/{base_records['request_id']}/gastos/{expense['id']}/particiones/me", headers=admin, json={
        "particiones": [{"categoria": "Agua", "monto": "30.00", "impuesto": "0"}, {"categoria": "Papelería", "monto": "70.00", "impuesto": "16"}],
    })
    assert split.status_code == 200, split.text
    child = next(item for item in split.json()["gastos"] if item["esHijoParticion"])
    assert child["idOriginal"] == expense["id"]
    assert datetime.fromisoformat(child["createdAt"]).date() == datetime.now(UTC).date()
    assert child["canAddObservation"] is True
    with session_factory() as db:
        db.get(ReimbursementRequest, UUID(base_records["request_id"])).status = ReimbursementRequestStatus.correction_required
        db.commit()
    for expense_id, note in [(expense["id"], "Original comment"), (child["backendId"], "Partition comment")]:
        response = client.post(f"/api/v1/expenses/{expense_id}/observation/me", headers=store, json={"note": note})
        assert response.status_code == 200, response.text
    notes = client.get(_path(base_records), headers=admin, params={"observations_only": True}).json()
    assert {row["message"]: row["expense_id"] for row in notes if row["action"] == "expense_observation_added"} == {
        "Original comment": expense["id"], "Partition comment": child["backendId"],
    }


def test_comment_retries_are_idempotent_but_identical_intentional_comments_are_kept(client, base_records):
    expense = create_expense(client, base_records)
    _, headers = _actor(client, base_records, "store")
    payload = {"note": "Comentario repetido a propósito", "eventId": str(uuid4())}
    path = f"/api/v1/expenses/{expense['id']}/observation/me"
    for _ in range(3):
        response = client.post(path, headers=headers, json=payload)
        assert response.status_code == 200, response.text
    conflict = client.post(path, headers=headers, json={**payload, "note": "No debe sobrescribirse"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "OBSERVATION_EVENT_CONFLICT"
    another = client.post(path, headers=headers, json={**payload, "eventId": str(uuid4())})
    assert another.status_code == 200, another.text
    rows = client.get(_path(base_records), headers=headers, params={"observations_only": True}).json()
    assert len(rows) == 2
    assert len({row["id"] for row in rows}) == 2
    assert all(row["message"] == payload["note"] for row in rows)
    assert client.post(path, headers=headers, json={"note": "   ", "eventId": str(uuid4())}).status_code == 422


def test_comment_event_cannot_be_reused_for_another_expense(client, base_records):
    first = create_expense(client, base_records)
    second = create_expense(client, base_records)
    _, headers = _actor(client, base_records, "store")
    payload = {"note": "Vinculado al gasto correcto", "eventId": str(uuid4())}
    assert client.post(f"/api/v1/expenses/{first['id']}/observation/me", headers=headers, json=payload).status_code == 200
    assert client.post(f"/api/v1/expenses/{second['id']}/observation/me", headers=headers, json=payload).status_code == 409
    rows = client.get(_path(base_records), headers=headers, params={"observations_only": True}).json()
    assert len(rows) == 1 and rows[0]["expense_id"] == first["id"]


def test_saved_comment_retry_acknowledges_previous_write_without_opening_a_closed_stage(client, base_records, session_factory):
    expense = create_expense(client, base_records)
    _, headers = _actor(client, base_records, "store")
    payload = {"note": "Ya se guardó antes de cambiar la etapa", "eventId": str(uuid4())}
    path = f"/api/v1/expenses/{expense['id']}/observation/me"
    assert client.post(path, headers=headers, json=payload).status_code == 200
    with session_factory() as db:
        db.get(ReimbursementRequest, UUID(base_records["request_id"])).status = ReimbursementRequestStatus.paid
        db.commit()
    assert client.post(path, headers=headers, json=payload).status_code == 200
    assert client.post(path, headers=headers, json={**payload, "eventId": str(uuid4())}).status_code == 409
    rows = client.get(_path(base_records), headers=headers, params={"observations_only": True}).json()
    assert len(rows) == 1


def test_concurrent_comment_retries_save_one_event(client, base_records, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.api.v1.endpoints import expenses

    expense = create_expense(client, base_records)
    _, headers = _actor(client, base_records, "store")
    barrier = Barrier(2)
    already_saved = expenses._observation_already_saved

    def simultaneous_read(db, audit_id, item, actor, note):
        exists = already_saved(db, audit_id, item, actor, note)
        if not exists:
            barrier.wait(timeout=10)
        return exists

    monkeypatch.setattr(expenses, "_observation_already_saved", simultaneous_read)
    payload = {"note": "Un solo envío concurrente", "eventId": str(uuid4())}
    path = f"/api/v1/expenses/{expense['id']}/observation/me"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(client.post, path, headers=headers, json=payload) for _ in range(2)]
        responses = [future.result(timeout=20) for future in futures]
    assert [response.status_code for response in responses] == [200, 200]
    rows = client.get(_path(base_records), headers=headers, params={"observations_only": True}).json()
    assert len(rows) == 1 and rows[0]["message"] == payload["note"]
