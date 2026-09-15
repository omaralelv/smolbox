from fastapi.testclient import TestClient


def test_admin_can_assign_authorization_area_only_to_authorizers(
    client: TestClient,
) -> None:
    admin_id = _create_user(client, "admin", "areas.admin@example.com")
    authorizer_id = _create_user(client, "authorizer", "areas.supervisor@example.com")
    accountant_id = _create_user(client, "accountant", "areas.conta@example.com")
    admin_headers = _auth_headers(client, "areas.admin@example.com")

    assignment = client.post(
        f"/api/v1/authorization-areas/users/{authorizer_id}",
        headers=admin_headers,
        json={"areaName": "Sistemas"},
    )
    assert assignment.status_code == 201, assignment.text
    assert assignment.json()["user_id"] == authorizer_id
    assert assignment.json()["authorization_area"]["name"] == "Sistemas"

    assignments = client.get(
        f"/api/v1/authorization-areas/users/{authorizer_id}",
        headers=admin_headers,
    )
    assert assignments.status_code == 200, assignments.text
    assert [item["authorization_area"]["name"] for item in assignments.json()] == ["Sistemas"]

    invalid_assignment = client.post(
        f"/api/v1/authorization-areas/users/{accountant_id}",
        headers=admin_headers,
        json={"areaName": "Sistemas"},
    )
    assert invalid_assignment.status_code == 422, invalid_assignment.text
    assert invalid_assignment.json()["detail"]["code"] == "USER_NOT_AUTHORIZER"
    assert admin_id


def test_authorizers_only_handle_expenses_for_their_authorization_area(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    _create_user(client, "admin", "areas.flow.admin@example.com")
    store_user_id = _create_user(client, "store", "areas.flow.store@example.com")
    systems_authorizer_id = _create_user(
        client,
        "authorizer",
        "areas.flow.sistemas@example.com",
    )
    hr_authorizer_id = _create_user(
        client,
        "authorizer",
        "areas.flow.rh@example.com",
    )
    accountant_id = _create_user(
        client,
        "accountant",
        "areas.flow.conta@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(
        client,
        base_records["store_id"],
        systems_authorizer_id,
        "authorizer",
    )
    _assign_user_to_store(
        client,
        base_records["store_id"],
        hr_authorizer_id,
        "authorizer",
    )
    _assign_user_to_store(client, base_records["store_id"], accountant_id, "accountant")

    admin_headers = _auth_headers(client, "areas.flow.admin@example.com")
    systems_area_id = _assign_authorization_area(
        client,
        systems_authorizer_id,
        "Sistemas",
        admin_headers,
    )
    hr_area_id = _assign_authorization_area(
        client,
        hr_authorizer_id,
        "Recursos Humanos",
        admin_headers,
    )

    systems_expense = _create_expense(
        client,
        base_records,
        amount="1000.00",
        authorization_area_id=systems_area_id,
    )
    hr_expense = _create_expense(
        client,
        base_records,
        amount="500.00",
        authorization_area_id=hr_area_id,
    )
    _attach_valid_cfdi(
        client,
        systems_expense["id"],
        "1000.00",
        uuid="77777777-7777-4777-8777-777777777777",
    )
    _attach_valid_cfdi(
        client,
        hr_expense["id"],
        "500.00",
        uuid="88888888-8888-4888-8888-888888888888",
    )

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    systems_headers = _auth_headers(client, "areas.flow.sistemas@example.com")
    hr_headers = _auth_headers(client, "areas.flow.rh@example.com")
    accountant_headers = _auth_headers(client, "areas.flow.conta@example.com")

    systems_queue = client.get("/api/v1/frontend/bandeja/me", headers=systems_headers)
    assert systems_queue.status_code == 200, systems_queue.text
    assert [item["backendId"] for item in systems_queue.json()] == [
        base_records["request_id"]
    ]
    assert [expense["authorizationArea"] for expense in systems_queue.json()[0]["gastos"]] == [
        "Sistemas"
    ]

    hr_queue = client.get("/api/v1/frontend/bandeja/me", headers=hr_headers)
    assert hr_queue.status_code == 200, hr_queue.text
    assert [item["backendId"] for item in hr_queue.json()] == [base_records["request_id"]]
    assert [expense["authorizationArea"] for expense in hr_queue.json()[0]["gastos"]] == [
        "Recursos Humanos"
    ]

    accountant_queue = client.get("/api/v1/frontend/bandeja/me", headers=accountant_headers)
    assert accountant_queue.status_code == 200, accountant_queue.text
    assert accountant_queue.json() == []

    authorization_review = _transition(
        client,
        base_records["request_id"],
        "authorization_review",
        systems_authorizer_id,
    )
    assert authorization_review.status_code == 200, authorization_review.text

    forbidden_expense = client.post(
        f"/api/v1/expenses/{hr_expense['id']}/authorize/me",
        headers=systems_headers,
        json={"note": "Intento de otra área"},
    )
    assert forbidden_expense.status_code == 403, forbidden_expense.text
    assert forbidden_expense.json()["detail"]["code"] == "AUTHORIZATION_AREA_FORBIDDEN"

    authorized_systems = client.post(
        f"/api/v1/expenses/{systems_expense['id']}/authorize/me",
        headers=systems_headers,
        json={"note": "Autorizado por Sistemas"},
    )
    assert authorized_systems.status_code == 200, authorized_systems.text

    systems_queue_after_authorizing = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=systems_headers,
    )
    assert systems_queue_after_authorizing.status_code == 200
    assert systems_queue_after_authorizing.json() == []

    hr_queue_after_systems = client.get("/api/v1/frontend/bandeja/me", headers=hr_headers)
    assert hr_queue_after_systems.status_code == 200, hr_queue_after_systems.text
    assert [item["backendId"] for item in hr_queue_after_systems.json()] == [
        base_records["request_id"]
    ]

    authorized_hr = client.post(
        f"/api/v1/expenses/{hr_expense['id']}/authorize/me",
        headers=hr_headers,
        json={"note": "Autorizado por Recursos Humanos"},
    )
    assert authorized_hr.status_code == 200, authorized_hr.text

    ready_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=hr_headers,
    )
    assert ready_detail.status_code == 200, ready_detail.text
    assert "approve_authorization" in ready_detail.json()["availableActions"]

    authorized_request = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=hr_headers,
        json={
            "target_status": "authorized",
            "note": "Autorización por áreas completa",
        },
    )
    assert authorized_request.status_code == 200, authorized_request.text

    accountant_queue_after_authorization = client.get(
        "/api/v1/frontend/bandeja/me",
        headers=accountant_headers,
    )
    assert accountant_queue_after_authorization.status_code == 200
    assert [item["backendId"] for item in accountant_queue_after_authorization.json()] == [
        base_records["request_id"]
    ]


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


def _assign_authorization_area(
    client: TestClient,
    user_id: str,
    area_name: str,
    headers: dict[str, str],
) -> str:
    response = client.post(
        f"/api/v1/authorization-areas/users/{user_id}",
        headers=headers,
        json={"areaName": area_name},
    )
    assert response.status_code == 201, response.text
    return response.json()["authorization_area_id"]


def _create_expense(
    client: TestClient,
    base_records: dict[str, str],
    *,
    amount: str,
    authorization_area_id: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor Demo",
            "amount": amount,
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Pasajes y Taxis",
            "authorization_area_id": authorization_area_id,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["requires_authorization"] is True
    return response.json()


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
    uuid: str,
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


def _cfdi_xml(amount: str, *, uuid: str) -> bytes:
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
