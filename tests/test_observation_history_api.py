from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from conftest import authenticated_audit_headers, create_expense

from app.models.audit_log import AuditActorType, AuditLog
from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus


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
