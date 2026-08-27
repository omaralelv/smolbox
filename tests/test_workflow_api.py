from uuid import uuid4

from conftest import create_expense
from fastapi.testclient import TestClient


def _create_user(client: TestClient, role: str) -> str:
    response = client.post(
        "/api/v1/users/",
        json={
            "email": f"{role}@example.com",
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
    *,
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


def _auth_headers(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret-password"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _cfdi_xml(amount: str, uuid: str = "11111111-2222-4333-8444-555555555555") -> bytes:
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


def _attach_valid_cfdi(client: TestClient, expense_id: str, amount: str) -> None:
    cfdi = client.post(
        f"/api/v1/expenses/{expense_id}/cfdi/validate",
        files={
            "file": (
                "invoice.xml",
                _cfdi_xml(amount, uuid=str(uuid4())),
                "application/xml",
            )
        },
    )
    assert cfdi.status_code == 200, cfdi.text
    assert cfdi.json()["is_valid"] is True


def test_store_submission_requires_cfdi_but_not_receipt(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")

    store_user_id = _create_user(client, "store")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")

    blocked = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"
    assert "valid CFDI evidence" in blocked.json()["detail"]["message"]

    _attach_valid_cfdi(client, expense["id"], "1500.00")
    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"


def test_request_moves_through_submission_and_accounting_review(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    receipt = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    accountant_user_id = _create_user(client, "accountant")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "submitted"

    authorization_review = _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    )
    assert authorization_review.status_code == 409
    assert authorization_review.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"
    assert "does not have expenses pending authorization" in authorization_review.json()["detail"][
        "message"
    ]

    review = _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=accountant_user_id,
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "under_accounting_review"

    accounting_reviewed = _transition(
        client,
        base_records["request_id"],
        target_status="accounting_reviewed",
        actor_user_id=accountant_user_id,
    )
    assert accounting_reviewed.status_code == 200, accounting_reviewed.text
    assert accounting_reviewed.json()["status"] == "accounting_reviewed"

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200
    actions = {event["action"] for event in audit_events.json()}
    assert "request_status_changed" in actions
    assert "expense_attachment_uploaded" in actions


def test_required_expense_authorization_blocks_request(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor con Autorizacion",
            "amount": "1500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert expense.status_code == 201, expense.text
    receipt = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense.json()["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    authorization_review = _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    )
    assert authorization_review.status_code == 200, authorization_review.text

    blocked = _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    authorized_expense = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/authorize",
        json={"actor_user_id": authorizer_user_id, "note": "Autorizado por area"},
    )
    assert authorized_expense.status_code == 200, authorized_expense.text
    assert authorized_expense.json()["authorized_at"] is not None

    authorized = _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["status"] == "authorized"


def test_authorization_rejects_only_the_expense_and_request_can_continue(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    approved_expense = create_expense(client, base_records, amount="1000.00")
    authorization_expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Producto no procedente",
            "amount": "500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert authorization_expense.status_code == 201, authorization_expense.text
    for expense_id in [approved_expense["id"], authorization_expense.json()["id"]]:
        receipt = client.post(
            f"/api/v1/expenses/{expense_id}/attachments",
            data={"attachment_type": "receipt"},
            files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
        )
        assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, approved_expense["id"], "1000.00")
    _attach_valid_cfdi(client, authorization_expense.json()["id"], "500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")

    assert (
        _transition(
            client,
            base_records["request_id"],
            target_status="submitted",
            actor_user_id=store_user_id,
        ).status_code
        == 200
    )
    assert (
        _transition(
            client,
            base_records["request_id"],
            target_status="authorization_review",
            actor_user_id=authorizer_user_id,
        ).status_code
        == 200
    )

    rejected_expense = client.post(
        f"/api/v1/expenses/{authorization_expense.json()['id']}/reject",
        json={
            "actor_user_id": authorizer_user_id,
            "reason": "Producto no autorizado para reembolso",
            "adjust_reported_total": True,
        },
    )
    assert rejected_expense.status_code == 200, rejected_expense.text
    assert rejected_expense.json()["status"] == "rejected"
    assert rejected_expense.json()["authorization_note"] == "Producto no autorizado para reembolso"

    summary = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/validation-summary"
    )
    assert summary.status_code == 200
    assert summary.json()["reported_total"] == "1000.00"
    assert summary.json()["calculated_total"] == "1000.00"
    assert authorization_expense.json()["id"] in summary.json()["rejected_expense_ids"]
    assert summary.json()["missing_authorization_expense_ids"] == []

    rejected_request = _transition(
        client,
        base_records["request_id"],
        target_status="rejected",
        actor_user_id=authorizer_user_id,
    )
    assert rejected_request.status_code == 409

    authorized = _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["status"] == "authorized"

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200
    assert "expense_authorization_rejected" in {
        event["action"] for event in audit_events.json()
    }


def test_authorization_can_reject_request_when_all_expenses_are_rejected(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Producto No Reembolsable",
            "amount": "1500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "transporte",
            "requires_authorization": True,
        },
    )
    assert expense.status_code == 201, expense.text
    receipt = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense.json()["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    authorization_review = _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    )
    assert authorization_review.status_code == 200, authorization_review.text

    rejected_expense = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/reject",
        json={
            "actor_user_id": authorizer_user_id,
            "reason": "No procede ningun producto de la solicitud",
            "adjust_reported_total": True,
        },
    )
    assert rejected_expense.status_code == 200, rejected_expense.text

    summary = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/validation-summary"
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["reported_total"] == "0.00"
    assert summary.json()["calculated_total"] == "0.00"
    assert summary.json()["expense_count"] == 0
    assert "no_payable_expenses" in {issue["code"] for issue in summary.json()["issues"]}

    rejected_request = _transition(
        client,
        base_records["request_id"],
        target_status="rejected",
        actor_user_id=authorizer_user_id,
    )
    assert rejected_request.status_code == 200, rejected_request.text
    assert rejected_request.json()["status"] == "rejected"
    assert rejected_request.json()["authorization_reviewed_at"] is not None

    blocked_authorized = _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    )
    assert blocked_authorized.status_code == 409


def test_accounting_can_remove_expense_with_reason(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    first_expense = create_expense(client, base_records, amount="1000.00")
    second_expense_response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Gasto autorizado removible",
            "amount": "500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert second_expense_response.status_code == 201, second_expense_response.text
    second_expense = second_expense_response.json()
    for expense in [first_expense, second_expense]:
        receipt = client.post(
            f"/api/v1/expenses/{expense['id']}/attachments",
            data={"attachment_type": "receipt"},
            files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
        )
        assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, first_expense["id"], "1000.00")
    _attach_valid_cfdi(client, second_expense["id"], "500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    accountant_user_id = _create_user(client, "accountant")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    assert _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    ).status_code == 200
    authorized_expense = client.post(
        f"/api/v1/expenses/{second_expense['id']}/authorize",
        json={"actor_user_id": authorizer_user_id, "note": "Autorizado antes de contabilidad"},
    )
    assert authorized_expense.status_code == 200, authorized_expense.text
    assert _transition(
        client,
        base_records["request_id"],
        target_status="authorized",
        actor_user_id=authorizer_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=accountant_user_id,
    ).status_code == 200
    premature_rejected = _transition(
        client,
        base_records["request_id"],
        target_status="rejected",
        actor_user_id=accountant_user_id,
    )
    assert premature_rejected.status_code == 409

    removed = client.post(
        f"/api/v1/expenses/{second_expense['id']}/remove",
        json={
            "actor_user_id": accountant_user_id,
            "reason": "Factura no procede",
            "adjust_reported_total": True,
        },
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "removed"
    assert removed.json()["requires_authorization"] is True
    assert removed.json()["removal_reason"] == "Factura no procede"

    summary = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/validation-summary"
    )
    assert summary.status_code == 200
    assert summary.json()["expense_count"] == 1
    assert summary.json()["calculated_total"] == "1000.00"
    assert summary.json()["reported_total"] == "1000.00"
    assert second_expense["id"] in summary.json()["removed_expense_ids"]

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200
    removal_event = next(
        event for event in audit_events.json() if event["action"] == "expense_removed_from_request"
    )
    assert removal_event["message"] == "Factura no procede"
    assert removal_event["event_payload"]["original_amount"] == "500.00"
    assert removal_event["event_payload"]["original_merchant"] == second_expense["merchant"]
    assert removal_event["event_payload"]["previous_expense_status"] == "approved"


def test_authorizer_removing_last_payable_expense_rejects_request(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Producto removible en autorizacion",
            "amount": "1500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert expense.status_code == 201, expense.text
    receipt = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense.json()["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text
    authorization_review = _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    )
    assert authorization_review.status_code == 200, authorization_review.text

    removed = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/remove/me",
        headers=_auth_headers(client, "authorizer@example.com"),
        json={
            "reason": "Producto no debe formar parte del reembolso",
            "adjust_reported_total": True,
        },
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["status"] == "removed"
    assert removed.json()["requires_authorization"] is True

    summary = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/validation-summary"
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["reported_total"] == "0.00"
    assert summary.json()["expense_count"] == 0
    assert expense.json()["id"] in summary.json()["removed_expense_ids"]
    assert "no_payable_expenses" in {issue["code"] for issue in summary.json()["issues"]}

    rejected_request = client.get(f"/api/v1/reimbursement-requests/{base_records['request_id']}")
    assert rejected_request.status_code == 200, rejected_request.text
    assert rejected_request.json()["status"] == "rejected"


def test_authorizer_cannot_remove_regular_expense_during_authorization_review(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1000.00")
    authorization_expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Producto que habilita autorizacion",
            "amount": "500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert authorization_expense.status_code == 201, authorization_expense.text
    for expense_id in [expense["id"], authorization_expense.json()["id"]]:
        receipt = client.post(
            f"/api/v1/expenses/{expense_id}/attachments",
            data={"attachment_type": "receipt"},
            files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
        )
        assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense["id"], "1000.00")
    _attach_valid_cfdi(client, authorization_expense.json()["id"], "500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")

    assert _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="authorization_review",
        actor_user_id=authorizer_user_id,
    ).status_code == 200

    removed = client.post(
        f"/api/v1/expenses/{expense['id']}/remove",
        json={
            "actor_user_id": authorizer_user_id,
            "reason": "Intento de quitar gasto normal",
            "adjust_reported_total": True,
        },
    )
    assert removed.status_code == 409
    assert removed.json()["detail"]["code"] == "EXPENSE_NOT_AUTHORIZATION_REQUIRED"


def test_authenticated_transition_uses_token_user_and_blocks_wrong_role(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Producto con Autorizacion Token",
            "amount": "1500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert expense.status_code == 201, expense.text
    receipt = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense.json()["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")

    store_headers = _auth_headers(client, "store@example.com")
    submitted = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=store_headers,
        json={"target_status": "submitted", "note": "Store submits with token"},
    )
    assert submitted.status_code == 200, submitted.text

    wrong_role = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=store_headers,
        json={"target_status": "authorization_review", "note": "Store cannot authorize"},
    )
    assert wrong_role.status_code == 409
    assert wrong_role.json()["detail"]["code"] == "INVALID_WORKFLOW_TRANSITION"

    authorizer_headers = _auth_headers(client, "authorizer@example.com")
    authorized_review = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=authorizer_headers,
        json={
            "target_status": "authorization_review",
            "actor_user_id": store_user_id,
            "note": "Body actor_user_id must be ignored",
        },
    )
    assert authorized_review.status_code == 200, authorized_review.text

    audit_events = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events"
    )
    assert audit_events.status_code == 200
    transition_events = [
        event for event in audit_events.json() if event["action"] == "request_status_changed"
    ]
    assert any(
        event["to_status"] == "authorization_review"
        and event["actor_user_id"] == authorizer_user_id
        for event in transition_events
    )


def test_authenticated_actions_require_store_assignment_and_role(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Producto con Autorizacion",
            "amount": "1500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert expense.status_code == 201, expense.text
    receipt = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense.json()["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    assigned_authorizer_id = _create_user(client, "authorizer")
    unassigned_authorizer = client.post(
        "/api/v1/users/",
        json={
            "email": "unassigned.authorizer@example.com",
            "full_name": "Unassigned Authorizer",
            "role": "authorizer",
            "password": "secret-password",
        },
    )
    assert unassigned_authorizer.status_code == 201, unassigned_authorizer.text
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(
        client,
        base_records["store_id"],
        assigned_authorizer_id,
        "authorizer",
    )

    assert _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    ).status_code == 200

    unassigned_headers = _auth_headers(client, "unassigned.authorizer@example.com")
    blocked_assignment = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=unassigned_headers,
        json={"target_status": "authorization_review"},
    )
    assert blocked_assignment.status_code == 403
    assert blocked_assignment.json()["detail"]["code"] == "STORE_ASSIGNMENT_REQUIRED"

    assigned_headers = _auth_headers(client, "authorizer@example.com")
    assert client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=assigned_headers,
        json={"target_status": "authorization_review"},
    ).status_code == 200

    store_headers = _auth_headers(client, "store@example.com")
    wrong_role = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/authorize/me",
        headers=store_headers,
        json={"note": "Store should not authorize"},
    )
    assert wrong_role.status_code == 409
    assert wrong_role.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"

    authorized = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/authorize/me",
        headers=assigned_headers,
        json={"note": "Authorized with token"},
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["authorized_by_user_id"] == assigned_authorizer_id


def test_work_queue_filters_by_role_status_and_store_assignment(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    receipt = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    accountant_user_id = _create_user(client, "accountant")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    store_queue = client.get("/api/v1/work-queue/me", headers=_auth_headers(client, "store@example.com"))
    assert store_queue.status_code == 200, store_queue.text
    assert [item["id"] for item in store_queue.json()] == [base_records["request_id"]]

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    authorizer_queue = client.get(
        "/api/v1/work-queue/me",
        headers=_auth_headers(client, "authorizer@example.com"),
    )
    assert authorizer_queue.status_code == 200, authorizer_queue.text
    assert authorizer_queue.json() == []

    accountant_queue = client.get(
        "/api/v1/work-queue/me",
        headers=_auth_headers(client, "accountant@example.com"),
    )
    assert accountant_queue.status_code == 200, accountant_queue.text
    assert [item["id"] for item in accountant_queue.json()] == [base_records["request_id"]]


def test_work_queue_routes_authorization_required_submitted_requests_to_authorizer(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor con Autorizacion",
            "amount": "1500.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "operacion",
            "requires_authorization": True,
        },
    )
    assert expense.status_code == 201, expense.text
    receipt = client.post(
        f"/api/v1/expenses/{expense.json()['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense.json()["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    authorizer_user_id = _create_user(client, "authorizer")
    accountant_user_id = _create_user(client, "accountant")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], authorizer_user_id, "authorizer")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")

    submitted = _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    )
    assert submitted.status_code == 200, submitted.text

    authorizer_queue = client.get(
        "/api/v1/work-queue/me",
        headers=_auth_headers(client, "authorizer@example.com"),
    )
    assert authorizer_queue.status_code == 200, authorizer_queue.text
    assert [item["id"] for item in authorizer_queue.json()] == [base_records["request_id"]]

    accountant_queue = client.get(
        "/api/v1/work-queue/me",
        headers=_auth_headers(client, "accountant@example.com"),
    )
    assert accountant_queue.status_code == 200, accountant_queue.text
    assert accountant_queue.json() == []


def test_later_review_returns_correction_to_accounting(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    receipt = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    cfdi = client.post(
        f"/api/v1/expenses/{expense['id']}/cfdi/validate",
        files={"file": ("invoice.xml", _cfdi_xml("1500.00"), "application/xml")},
    )
    assert cfdi.status_code == 200, cfdi.text
    assert cfdi.json()["is_valid"] is True

    store_user_id = _create_user(client, "store")
    accountant_user_id = _create_user(client, "accountant")
    manager_user_id = _create_user(client, "accounting_manager")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")
    _assign_user_to_store(
        client,
        base_records["store_id"],
        manager_user_id,
        "accounting_manager",
    )

    assert _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=accountant_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_reviewed",
        actor_user_id=accountant_user_id,
    ).status_code == 200

    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/sap-policy/prepare",
        json={
            "actor_user_id": accountant_user_id,
            "reference": "SAP-REWORK-001",
            "note": "Preparado antes de gerente.",
        },
    )
    assert sap_policy.status_code == 200, sap_policy.text

    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_review",
        actor_user_id=manager_user_id,
    ).status_code == 200

    blocked_store_correction = _transition(
        client,
        base_records["request_id"],
        target_status="correction_required",
        actor_user_id=manager_user_id,
    )
    assert blocked_store_correction.status_code == 409

    returned = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition",
        json={
            "target_status": "under_accounting_review",
            "actor_user_id": manager_user_id,
            "note": "Gerente pide ajuste a contabilidad.",
        },
    )
    assert returned.status_code == 200, returned.text
    assert returned.json()["status"] == "under_accounting_review"
    assert returned.json()["correction_return_status"] == "under_accounting_review"
    assert returned.json()["correction_reason"] == "Gerente pide ajuste a contabilidad."

    store_queue = client.get(
        "/api/v1/work-queue/me",
        headers=_auth_headers(client, "store@example.com"),
    )
    assert store_queue.status_code == 200, store_queue.text
    assert store_queue.json() == []

    accountant_queue = client.get(
        "/api/v1/work-queue/me",
        headers=_auth_headers(client, "accountant@example.com"),
    )
    assert accountant_queue.status_code == 200, accountant_queue.text
    assert [item["id"] for item in accountant_queue.json()] == [base_records["request_id"]]


def test_frontend_payment_flow_returns_to_manager_for_confirmation(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    accountant_user_id = _create_user(client, "accountant")
    manager_user_id = _create_user(client, "accounting_manager")
    treasury_user_id = _create_user(client, "treasury")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")
    _assign_user_to_store(
        client,
        base_records["store_id"],
        manager_user_id,
        "accounting_manager",
    )
    _assign_user_to_store(client, base_records["store_id"], treasury_user_id, "treasury")

    assert _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=accountant_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_reviewed",
        actor_user_id=accountant_user_id,
    ).status_code == 200

    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/sap-policy/prepare",
        json={
            "actor_user_id": accountant_user_id,
            "reference": "SAP-FRONTEND-PAYMENT-FLOW",
            "note": "Preparado antes de gerencia.",
        },
    )
    assert sap_policy.status_code == 200, sap_policy.text

    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_review",
        actor_user_id=manager_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_approved",
        actor_user_id=manager_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="treasury_review",
        actor_user_id=treasury_user_id,
    ).status_code == 200

    treasury_approved = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=_auth_headers(client, "treasury@example.com"),
        json={
            "target_status": "direction_approved",
            "note": "Tesoreria aprueba pago para gerencia.",
        },
    )
    assert treasury_approved.status_code == 200, treasury_approved.text
    assert treasury_approved.json()["status"] == "direction_approved"

    manager_headers = _auth_headers(client, "accounting_manager@example.com")
    manager_queue = client.get("/api/v1/frontend/bandeja/me", headers=manager_headers)
    assert manager_queue.status_code == 200, manager_queue.text
    assert [item["backendId"] for item in manager_queue.json()] == [base_records["request_id"]]
    assert manager_queue.json()[0]["availableActions"] == ["mark_approved_for_payment"]

    approved_for_payment = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/transition/me",
        headers=manager_headers,
        json={
            "target_status": "approved_for_payment",
            "note": "Gerencia habilita confirmacion de pago.",
        },
    )
    assert approved_for_payment.status_code == 200, approved_for_payment.text
    assert approved_for_payment.json()["status"] == "approved_for_payment"

    manager_detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers=manager_headers,
    )
    assert manager_detail.status_code == 200, manager_detail.text
    assert manager_detail.json()["availableActions"] == ["record_payment"]

    payment = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/payments/me",
        headers=manager_headers,
        json={"reference": "PAGO-GERENCIA-001", "note": "Pago confirmado por gerencia."},
    )
    assert payment.status_code == 201, payment.text
    assert payment.json()["amount"] == "1500.00"

    paid_request = client.get(f"/api/v1/reimbursement-requests/{base_records['request_id']}")
    assert paid_request.status_code == 200, paid_request.text
    assert paid_request.json()["status"] == "paid"


def test_later_reviews_return_to_previous_step(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records, amount="1500.00")
    receipt = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert receipt.status_code == 201, receipt.text
    _attach_valid_cfdi(client, expense["id"], "1500.00")

    store_user_id = _create_user(client, "store")
    accountant_user_id = _create_user(client, "accountant")
    manager_user_id = _create_user(client, "accounting_manager")
    treasury_user_id = _create_user(client, "treasury")
    director_user_id = _create_user(client, "director")
    _assign_user_to_store(client, base_records["store_id"], store_user_id, "store")
    _assign_user_to_store(client, base_records["store_id"], accountant_user_id, "accountant")
    _assign_user_to_store(
        client,
        base_records["store_id"],
        manager_user_id,
        "accounting_manager",
    )
    _assign_user_to_store(client, base_records["store_id"], treasury_user_id, "treasury")
    _assign_user_to_store(client, base_records["store_id"], director_user_id, "director")

    assert _transition(
        client,
        base_records["request_id"],
        target_status="submitted",
        actor_user_id=store_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=accountant_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_reviewed",
        actor_user_id=accountant_user_id,
    ).status_code == 200

    sap_policy = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/sap-policy/prepare",
        json={
            "actor_user_id": accountant_user_id,
            "reference": "SAP-STEP-BACK-001",
            "note": "Preparado antes de gerente.",
        },
    )
    assert sap_policy.status_code == 200, sap_policy.text

    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_review",
        actor_user_id=manager_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_approved",
        actor_user_id=manager_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="treasury_review",
        actor_user_id=treasury_user_id,
    ).status_code == 200

    direct_accounting_return = _transition(
        client,
        base_records["request_id"],
        target_status="under_accounting_review",
        actor_user_id=treasury_user_id,
    )
    assert direct_accounting_return.status_code == 409

    returned_to_manager = _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_review",
        actor_user_id=treasury_user_id,
    )
    assert returned_to_manager.status_code == 200, returned_to_manager.text
    assert returned_to_manager.json()["status"] == "accounting_manager_review"
    assert returned_to_manager.json()["correction_return_status"] == "accounting_manager_review"

    assert _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_approved",
        actor_user_id=manager_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="treasury_review",
        actor_user_id=treasury_user_id,
    ).status_code == 200
    assert _transition(
        client,
        base_records["request_id"],
        target_status="direction_review",
        actor_user_id=treasury_user_id,
    ).status_code == 200

    direct_manager_return = _transition(
        client,
        base_records["request_id"],
        target_status="accounting_manager_review",
        actor_user_id=director_user_id,
    )
    assert direct_manager_return.status_code == 409

    returned_to_treasury = _transition(
        client,
        base_records["request_id"],
        target_status="treasury_review",
        actor_user_id=director_user_id,
    )
    assert returned_to_treasury.status_code == 200, returned_to_treasury.text
    assert returned_to_treasury.json()["status"] == "treasury_review"
    assert returned_to_treasury.json()["correction_return_status"] == "treasury_review"
