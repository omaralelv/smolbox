from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models.expense import Expense, ExpenseStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus


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
    assert systems_queue.json()[0]["authorizationPendingCount"] == 2
    assert systems_queue.json()[0]["readyForAuthorizationApproval"] is False
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
    assert hr_queue_after_systems.json()[0]["authorizationPendingCount"] == 1
    assert hr_queue_after_systems.json()[0]["readyForAuthorizationApproval"] is False

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
    assert ready_detail.json()["authorizationPendingCount"] == 0
    assert ready_detail.json()["readyForAuthorizationApproval"] is True

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


@pytest.mark.parametrize(
    "category",
    ["Equipo de Cómputo Menor", "Pasajes y Taxis", "No Deducibles", "No Deducible"],
)
def test_central_authorization_area_does_not_require_store_assignment(
    client: TestClient,
    base_records: dict[str, str],
    category: str,
) -> None:
    _create_user(client, "admin", "areas.central.admin@example.com")
    store_user_id = _create_user(client, "store", "areas.central.store@example.com")
    systems_authorizer_id = _create_user(
        client,
        "authorizer",
        "areas.central.sistemas@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")

    admin_headers = _auth_headers(client, "areas.central.admin@example.com")
    systems_area_id = _assign_authorization_area(
        client,
        systems_authorizer_id,
        "Sistemas",
        admin_headers,
    )
    systems_expense = _create_expense(
        client,
        base_records,
        amount="1000.00",
        authorization_area_id=systems_area_id,
        category=category,
    )
    _attach_valid_cfdi(
        client,
        systems_expense["id"],
        "1000.00",
        uuid="99999999-9999-4999-8999-999999999999",
    )
    uploaded_pdf = client.post(
        f"/api/v1/expenses/{systems_expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("invoice.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert uploaded_pdf.status_code == 201, uploaded_pdf.text

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    systems_headers = _auth_headers(client, "areas.central.sistemas@example.com")
    systems_queue = client.get("/api/v1/frontend/bandeja/me", headers=systems_headers)
    assert systems_queue.status_code == 200, systems_queue.text
    assert [item["backendId"] for item in systems_queue.json()] == [
        base_records["request_id"]
    ]
    assert [expense["authorizationArea"] for expense in systems_queue.json()[0]["gastos"]] == [
        "Sistemas"
    ]
    visible_expense = systems_queue.json()[0]["gastos"][0]
    for field, content_type in (("urlFactura", "application/xml"), ("urlRecibo", "application/pdf")):
        document = client.get(visible_expense[field], headers=systems_headers)
        assert document.status_code == 200, document.text
        assert document.headers["content-type"].startswith(content_type)

    api_queue = client.get("/api/v1/work-queue/me", headers=systems_headers)
    assert api_queue.status_code == 200, api_queue.text
    assert [item["id"] for item in api_queue.json()] == [base_records["request_id"]]

    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=systems_headers,
    )
    assert detail.status_code == 200, detail.text

    authorization_review = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=systems_headers,
        json={
            "target_status": "authorization_review",
            "note": "Inicio Sistemas",
        },
    )
    assert authorization_review.status_code == 200, authorization_review.text
    document = client.get(visible_expense["urlFactura"], headers=systems_headers)
    assert document.status_code == 200, document.text

    authorized_systems = client.post(
        f"/api/v1/expenses/{systems_expense['id']}/authorize/me",
        headers=systems_headers,
        json={"note": "Autorizado por Sistemas"},
    )
    assert authorized_systems.status_code == 200, authorized_systems.text


@pytest.mark.parametrize("category", ["Alimentos", "No Deducibles", "No Deducible"])
def test_supervisores_area_still_requires_store_assignment(
    client: TestClient,
    base_records: dict[str, str],
    category: str,
) -> None:
    _create_user(client, "admin", "areas.supervisores.admin@example.com")
    store_user_id = _create_user(client, "store", "areas.supervisores.store@example.com")
    supervisor_id = _create_user(
        client,
        "authorizer",
        "areas.supervisores.authorizer@example.com",
    )
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")

    admin_headers = _auth_headers(client, "areas.supervisores.admin@example.com")
    supervisor_area_id = _assign_authorization_area(
        client,
        supervisor_id,
        "Supervisores",
        admin_headers,
    )
    supervisor_expense = _create_expense(
        client,
        base_records,
        amount="500.00",
        authorization_area_id=supervisor_area_id,
        category=category,
    )
    _attach_valid_cfdi(
        client,
        supervisor_expense["id"],
        "500.00",
        uuid="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )

    submitted = _transition(
        client,
        base_records["request_id"],
        "submitted",
        store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    supervisor_headers = _auth_headers(client, "areas.supervisores.authorizer@example.com")
    supervisor_queue = client.get("/api/v1/frontend/bandeja/me", headers=supervisor_headers)
    assert supervisor_queue.status_code == 200, supervisor_queue.text
    assert supervisor_queue.json() == []

    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=supervisor_headers,
    )
    assert detail.status_code == 403, detail.text
    metadata = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me", headers=admin_headers,
    )
    document_url = metadata.json()["gastos"][0]["urlFactura"]
    download = client.get(
        document_url,
        headers=supervisor_headers,
    )
    assert download.status_code == 403, download.text

    _assign_user_to_store(client, base_records["store_id"], supervisor_id, "authorizer")
    visible = client.get("/api/v1/frontend/bandeja/me", headers=supervisor_headers)
    assert len(visible.json()) == 1
    download = client.get(visible.json()[0]["gastos"][0]["urlFactura"], headers=supervisor_headers)
    assert download.status_code == 200, download.text


@pytest.mark.parametrize("assigned_to_store", [False, True])
def test_authorizer_only_downloads_documents_for_visible_expenses(
    client: TestClient,
    base_records: dict[str, str],
    assigned_to_store: bool,
) -> None:
    _create_user(client, "admin", "documents.admin@example.com")
    store_user = _create_user(client, "store", "documents.store@example.com")
    systems_user = _create_user(client, "authorizer", "documents.systems@example.com")
    hr_user = _create_user(client, "authorizer", "documents.hr@example.com")
    _assign_user_to_store(client, base_records["store_id"], store_user, "store")
    if assigned_to_store:
        _assign_user_to_store(client, base_records["store_id"], systems_user, "authorizer")
    admin_headers = _auth_headers(client, "documents.admin@example.com")
    systems_area = _assign_authorization_area(client, systems_user, "Sistemas", admin_headers)
    hr_area = _assign_authorization_area(client, hr_user, "Recursos Humanos", admin_headers)
    systems_expense = _create_expense(
        client, base_records, amount="1000.00", authorization_area_id=systems_area,
    )
    hr_expense = _create_expense(
        client, base_records, amount="500.00", authorization_area_id=hr_area,
    )
    for expense, amount, uuid in (
        (systems_expense, "1000.00", "77777777-7777-4777-8777-777777777777"),
        (hr_expense, "500.00", "88888888-8888-4888-8888-888888888888"),
    ):
        _attach_valid_cfdi(client, expense["id"], amount, uuid=uuid)
    submitted = _transition(client, base_records["request_id"], "submitted", store_user)
    assert submitted.status_code == 200, submitted.text

    systems_headers = _auth_headers(client, "documents.systems@example.com")
    visible = client.get("/api/v1/frontend/bandeja/me", headers=systems_headers)
    assert visible.status_code == 200, visible.text
    assert [expense["id"] for expense in visible.json()[0]["gastos"]] == [systems_expense["id"]]
    own_url = visible.json()[0]["gastos"][0]["urlFactura"]
    own_document = client.get(own_url, headers=systems_headers)
    assert own_document.status_code == 200, own_document.text
    hr_metadata = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me", headers=admin_headers,
    )
    hr_document_url = next(
        expense["urlFactura"] for expense in hr_metadata.json()["gastos"]
        if expense["id"] == hr_expense["id"]
    )
    other_document = client.get(hr_document_url, headers=systems_headers)
    assert other_document.status_code == 403, other_document.text

    revoked = client.post(
        f"/api/v1/authorization-areas/users/{systems_user}", headers=admin_headers,
        json={"authorizationAreaId": systems_area, "is_active": False},
    )
    assert revoked.status_code == 201, revoked.text
    denied = client.get(own_url, headers=systems_headers)
    assert denied.status_code == 403, denied.text


def test_area_authorizer_can_download_shared_partition_evidence(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
) -> None:
    _create_user(client, "admin", "partition.docs.admin@example.com")
    systems_user = _create_user(client, "authorizer", "partition.docs.systems@example.com")
    hr_user = _create_user(client, "authorizer", "partition.docs.hr@example.com")
    admin_headers = _auth_headers(client, "partition.docs.admin@example.com")
    systems_area = _assign_authorization_area(client, systems_user, "Sistemas", admin_headers)
    hr_area = _assign_authorization_area(client, hr_user, "Recursos Humanos", admin_headers)
    parent = _create_expense(client, base_records, amount="1000.00", authorization_area_id=hr_area)
    _attach_valid_cfdi(
        client, parent["id"], "1000.00", uuid="99999999-9999-4999-8999-999999999999",
    )
    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.status = ReimbursementRequestStatus.authorization_review
        for index, area in enumerate((systems_area, hr_area), start=1):
            session.add(Expense(
                period_id=UUID(base_records["period_id"]), reimbursement_request_id=request.id,
                partition_parent_expense_id=UUID(parent["id"]), partition_index=index,
                partition_count=2, merchant="Proveedor Demo", amount=Decimal("500.00"),
                spent_on=date(2026, 8, 7), category="Pasajes y Taxis", requires_authorization=True,
                authorization_area_id=UUID(area), status=ExpenseStatus.submitted,
            ))
        session.commit()
    headers = _auth_headers(client, "partition.docs.systems@example.com")
    queue = client.get("/api/v1/frontend/bandeja/me", headers=headers)
    assert queue.status_code == 200, queue.text
    visible = queue.json()[0]["gastos"]
    assert len(visible) == 1
    assert visible[0]["idOriginal"] == parent["id"]
    document = client.get(visible[0]["urlFactura"], headers=headers)
    assert document.status_code == 200, document.text

    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(base_records["request_id"]))
        for expense in request.expenses:
            if expense.partition_parent_expense_id is not None:
                expense.status = ExpenseStatus.removed
        session.commit()
    denied = client.get(visible[0]["urlFactura"], headers=headers)
    assert denied.status_code == 403, denied.text


@pytest.mark.parametrize(
    ("request_status", "expected_status"),
    [
        (ReimbursementRequestStatus.draft, 403),
        (ReimbursementRequestStatus.submitted, 200),
        (ReimbursementRequestStatus.authorization_review, 200),
        (ReimbursementRequestStatus.under_accounting_review, 403),
    ],
)
def test_area_document_access_follows_request_visibility(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
    request_status: ReimbursementRequestStatus,
    expected_status: int,
) -> None:
    _create_user(client, "admin", "document.visibility.admin@example.com")
    authorizer = _create_user(client, "authorizer", "document.visibility.systems@example.com")
    admin_headers = _auth_headers(client, "document.visibility.admin@example.com")
    area = _assign_authorization_area(client, authorizer, "Sistemas", admin_headers)
    expense = _create_expense(client, base_records, amount="1000.00", authorization_area_id=area)
    _attach_valid_cfdi(
        client, expense["id"], "1000.00", uuid="99999999-9999-4999-8999-999999999999",
    )
    admin_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me", headers=admin_headers,
    )
    url = admin_detail.json()["gastos"][0]["urlFactura"]
    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.status = request_status
        session.commit()
    headers = _auth_headers(client, "document.visibility.systems@example.com")
    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me", headers=headers,
    )
    assert detail.status_code == expected_status, detail.text
    document = client.get(url, headers=headers)
    assert document.status_code == expected_status, document.text


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
    category: str = "Pasajes y Taxis",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor Demo",
            "amount": amount,
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": category,
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
