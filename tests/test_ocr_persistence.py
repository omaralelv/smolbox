from dataclasses import replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from conftest import authenticated_audit_headers, create_expense
from sqlalchemy import select

from app.models.expense import Expense, ExpenseStatus
from app.models.ocr_extraction import OcrExtraction, OcrExtractionStatus
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.services.authorization_areas import get_or_create_authorization_area
from app.services.ocr_preview import (
    build_ocr_preview_payload,
    sign_ocr_preview_payload,
    verify_ocr_preview_token,
)
from app.services.textract_ocr import (
    OCR_UNREADABLE_DOCUMENT_MESSAGE,
    TextractOcrError,
    TextractOcrResult,
    TextractOcrService,
)

PDF = b"%PDF-1.4\ncontent\n%%EOF"
RAW_RESPONSE = {
    "ExpenseDocuments": [{
        "Blocks": [{"BlockType": "LINE", "Text": "Total $100.00", "Confidence": 98.5}],
        "SummaryFields": [],
    }],
    "ResponseMetadata": {"RequestId": "saved-aws-request"},
}


@pytest.fixture
def saved_result(monkeypatch, test_settings):
    test_settings.textract_enabled = True
    result = TextractOcrResult(
        raw_text="COMERCIAL IAC\nCIA090819PW4\nFecha 07/08/2026\nTotal $100.00",
        extracted_total=Decimal("100.00"),
        extracted_date=date(2026, 8, 7),
        extracted_supplier="Proveedor Demo",
        suggested_cfdi_uuid="11111111-2222-3333-4444-AAAAAAAAAAAA",
        confidence=Decimal("98.50"),
        raw_response=RAW_RESPONSE,
    )
    monkeypatch.setattr(TextractOcrService, "extract_expense", lambda *args, **kwargs: result)
    return result


def _preview(client, **data):
    return client.post(
        "/api/v1/cfdi/ocr-preview", data=data,
        files={"file": ("factura.pdf", PDF, "application/pdf")},
    )


def _upload(client, expense, *, token=None, content=PDF):
    data = {"attachment_type": "receipt"}
    if token:
        data["ocr_preview_token"] = token
    response = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments", data=data,
        files={"file": ("factura.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assert_reading(extraction, result):
    assert extraction.raw_text == result.raw_text
    assert extraction.raw_response == result.raw_response
    assert extraction.extracted_total == result.extracted_total
    assert extraction.extracted_date == result.extracted_date
    assert extraction.extracted_supplier == result.extracted_supplier
    assert extraction.suggested_cfdi_uuid == result.suggested_cfdi_uuid
    assert extraction.confidence == result.confidence
    assert extraction.document_checksum_sha256 == sha256(PDF).hexdigest()
    assert extraction.source_filename == "factura.pdf"


def test_preview_saves_full_reading_before_expense_exists(
    client, saved_result, session_factory, test_settings,
):
    response = _preview(client)
    assert response.status_code == 200, response.text
    assert "raw_text" not in response.json()
    assert "raw_response" not in response.json()
    payload = verify_ocr_preview_token(
        response.json()["verification_token"], test_settings.auth_token_secret,
    )
    assert "raw_text" not in payload
    assert "raw_response" not in payload
    with session_factory() as session:
        extraction = session.scalars(select(OcrExtraction)).one()
        assert str(extraction.id) == payload["extraction_id"]
        assert extraction.attachment_id is None
        assert extraction.expense_id is None
        assert extraction.status == OcrExtractionStatus.succeeded
        _assert_reading(extraction, saved_result)


def test_wrong_receiver_does_not_discard_the_reading(
    client, saved_result, session_factory, test_settings,
):
    test_settings.invoice_ocr_receiver_name = "OTRA EMPRESA"
    response = _preview(client)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OCR_RECEIVER_MISMATCH"
    with session_factory() as session:
        _assert_reading(session.scalars(select(OcrExtraction)).one(), saved_result)


def test_failed_preview_saves_technical_error_without_changing_alert(
    client, monkeypatch, session_factory, test_settings,
):
    test_settings.textract_enabled = True

    def fail(*args, **kwargs):
        raise TextractOcrError("AccessDeniedException: test-request-id")

    monkeypatch.setattr(TextractOcrService, "extract_expense", fail)
    response = _preview(client)
    assert response.status_code == 502
    assert response.json()["detail"]["message"] == OCR_UNREADABLE_DOCUMENT_MESSAGE
    with session_factory() as session:
        extraction = session.scalars(select(OcrExtraction)).one()
        assert extraction.status == OcrExtractionStatus.failed
        assert "AccessDeniedException" in extraction.error_message
        assert extraction.document_checksum_sha256 == sha256(PDF).hexdigest()
        assert extraction.raw_response is None


@pytest.mark.parametrize("attach_directly", [False, True])
def test_empty_aws_reading_is_preserved_even_when_ocr_fails(
    client, base_records, monkeypatch, session_factory, test_settings, attach_directly,
):
    test_settings.textract_enabled = True

    class EmptyClient:
        def analyze_expense(self, Document):
            return {"ExpenseDocuments": [], "ResponseMetadata": {"RequestId": "empty-expense"}}

        def detect_document_text(self, Document):
            return {"Blocks": [], "ResponseMetadata": {"RequestId": "empty-text"}}

    monkeypatch.setattr(TextractOcrService, "_client", lambda self: EmptyClient())
    if attach_directly:
        uploaded = _upload(client, create_expense(client, base_records))
        assert uploaded["ocr_extraction"]["error_message"] == OCR_UNREADABLE_DOCUMENT_MESSAGE
    else:
        response = _preview(client, document_type="vale")
        assert response.status_code == 502
        assert response.json()["detail"]["message"] == OCR_UNREADABLE_DOCUMENT_MESSAGE
    with session_factory() as session:
        extraction = session.scalars(select(OcrExtraction)).one()
        assert extraction.status == OcrExtractionStatus.failed
        assert extraction.raw_text == ""
        assert len(extraction.raw_response["sources"]) == 2
        assert extraction.raw_response["sources"][0]["ResponseMetadata"]["RequestId"] == "empty-expense"


@pytest.mark.parametrize("reuse_preview", [False, True])
def test_upload_preserves_complete_result_and_original_file(
    client, base_records, saved_result, monkeypatch, session_factory, test_settings, reuse_preview,
):
    token = None
    if reuse_preview:
        preview = _preview(client)
        assert preview.status_code == 200, preview.text
        token = preview.json()["verification_token"]
        test_settings.textract_enabled = False

        def fail_if_called(*args, **kwargs):
            pytest.fail("Reusing a saved preview must not call AWS again")

        monkeypatch.setattr(TextractOcrService, "extract_expense", fail_if_called)
    uploaded = _upload(client, create_expense(client, base_records), token=token)
    assert "raw_text" not in uploaded["ocr_extraction"]
    assert "raw_response" not in uploaded["ocr_extraction"]
    download = client.get(f"/api/v1/attachments/{uploaded['id']}/download")
    assert download.content == PDF
    metadata = client.get(f"/api/v1/attachments/{uploaded['id']}")
    assert "raw_response" not in metadata.json()["ocr_extraction"]
    with session_factory() as session:
        rows = session.scalars(select(OcrExtraction)).all()
        assert len(rows) == (2 if reuse_preview else 1)
        for row in rows:
            _assert_reading(row, saved_result)
        attached = next(row for row in rows if row.attachment_id is not None)
        assert str(attached.attachment_id) == uploaded["id"]


@pytest.mark.parametrize("invalidity", ["other_file", "tampered", "missing_reading", "wrong_checksum"])
def test_invalid_preview_never_reuses_another_reading(
    client, base_records, saved_result, session_factory, test_settings, invalidity,
):
    response = _preview(client)
    token = response.json()["verification_token"]
    payload = verify_ocr_preview_token(token, test_settings.auth_token_secret)
    content = PDF
    if invalidity == "other_file":
        content = b"%PDF-1.4\nother\n%%EOF"
    elif invalidity == "tampered":
        token += "tampered"
    elif invalidity == "missing_reading":
        payload["extraction_id"] = str(uuid4())
        token = sign_ocr_preview_payload(payload, test_settings.auth_token_secret)
    else:
        with session_factory() as session:
            extraction = session.get(OcrExtraction, UUID(payload["extraction_id"]))
            extraction.document_checksum_sha256 = "0" * 64
            session.commit()
    test_settings.textract_enabled = False
    uploaded = _upload(client, create_expense(client, base_records), token=token, content=content)
    assert uploaded["ocr_extraction"] is None


def test_legacy_signed_preview_remains_usable_without_inventing_raw_data(
    client, base_records, test_settings,
):
    payload = build_ocr_preview_payload(
        checksum_sha256=sha256(PDF).hexdigest(), suggested_cfdi_uuid=None,
        extracted_total=Decimal("100.00"), extracted_date=date(2026, 8, 7),
        extracted_supplier="Proveedor Demo", confidence=Decimal("98.50"),
    )
    token = sign_ocr_preview_payload(payload, test_settings.auth_token_secret)
    uploaded = _upload(client, create_expense(client, base_records), token=token)
    assert uploaded["ocr_extraction"]["extracted_total"] == "100.00"


@pytest.mark.parametrize("role", ["store", "accountant", "admin"])
def test_saved_reading_requires_same_document_permissions(
    client, base_records, saved_result, role,
):
    uploaded = _upload(client, create_expense(client, base_records))
    endpoint = f"/api/v1/attachments/{uploaded['id']}/ocr/me"
    assert client.get(endpoint).status_code == 401
    email = f"ocr.{role}@example.com"
    user = client.post("/api/v1/users/", json={
        "email": email, "password": "secret-password", "full_name": "OCR Reader", "role": role,
    })
    assert user.status_code == 201, user.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    if role == "store":
        assert client.get(endpoint, headers=headers).status_code == 403
        assignment = client.post(f"/api/v1/stores/{base_records['store_id']}/users", json={
            "user_id": user.json()["id"], "role": "store",
        })
        assert assignment.status_code == 201, assignment.text
    response = client.get(endpoint, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["raw_text"] == saved_result.raw_text
    assert response.json()["raw_response"] == RAW_RESPONSE
    assert response.json()["document_checksum_sha256"] == sha256(PDF).hexdigest()


def test_missing_saved_reading_returns_404(client, base_records):
    uploaded = _upload(client, create_expense(client, base_records))
    headers = authenticated_audit_headers(client)
    assert client.get(f"/api/v1/attachments/{uploaded['id']}/ocr/me", headers=headers).status_code == 404
    assert client.get(f"/api/v1/attachments/{uuid4()}/ocr/me", headers=headers).status_code == 404


@pytest.mark.parametrize("partitioned", [False, True])
def test_authorizer_reading_access_follows_area_and_active_partitions(
    client, base_records, saved_result, session_factory, partitioned,
):
    admin_headers = authenticated_audit_headers(client)
    email = "ocr.authorizer@example.com"
    user = client.post("/api/v1/users/", json={
        "email": email, "password": "secret-password", "full_name": "OCR Area Reader",
        "role": "authorizer",
    })
    assert user.status_code == 201, user.text
    assignment = client.post(
        f"/api/v1/authorization-areas/users/{user.json()['id']}", headers=admin_headers,
        json={"areaName": "Sistemas"},
    )
    assert assignment.status_code == 201, assignment.text
    area_id = UUID(assignment.json()["authorization_area_id"])
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-password"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    parent = create_expense(client, base_records)
    other = create_expense(client, base_records)
    uploaded = _upload(client, parent)
    other_uploaded = _upload(client, other)
    with session_factory() as session:
        request = session.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.status = ReimbursementRequestStatus.authorization_review
        foreign_area = get_or_create_authorization_area(session, "Recursos Humanos")
        for expense_id in (parent["id"], other["id"]):
            expense = session.get(Expense, UUID(expense_id))
            expense.category = "Pasajes y Taxis"
            expense.requires_authorization = True
            expense.status = ExpenseStatus.submitted
            expense.authorization_area_id = foreign_area.id
        if partitioned:
            session.add(Expense(
                period_id=UUID(base_records["period_id"]), reimbursement_request_id=request.id,
                partition_parent_expense_id=UUID(parent["id"]), partition_index=1,
                partition_count=1, merchant="Particion", amount=Decimal("123.45"),
                spent_on=date(2026, 8, 7), category="Pasajes y Taxis", requires_authorization=True,
                authorization_area_id=area_id, status=ExpenseStatus.submitted,
            ))
        else:
            session.get(Expense, UUID(parent["id"])).authorization_area_id = area_id
        session.commit()
    endpoint = f"/api/v1/attachments/{uploaded['id']}/ocr/me"
    own_reading = client.get(endpoint, headers=headers)
    assert own_reading.status_code == 200, own_reading.text
    assert own_reading.json()["raw_text"] == saved_result.raw_text
    assert client.get(
        f"/api/v1/attachments/{other_uploaded['id']}/ocr/me", headers=headers,
    ).status_code == 403
    if partitioned:
        with session_factory() as session:
            child = session.scalars(select(Expense).where(
                Expense.partition_parent_expense_id == UUID(parent["id"]),
            )).one()
            child.status = ExpenseStatus.removed
            session.commit()
    else:
        revoked = client.post(
            f"/api/v1/authorization-areas/users/{user.json()['id']}", headers=admin_headers,
            json={"authorizationAreaId": str(area_id), "is_active": False},
        )
        assert revoked.status_code == 201, revoked.text
    assert client.get(endpoint, headers=headers).status_code == 403


@pytest.mark.parametrize("document_type", ["factura", "vale", "recibo"])
def test_receiver_tolerance_keeps_original_reading_and_signed_preview_reuse(
    client, base_records, saved_result, session_factory, monkeypatch, document_type,
):
    result = replace(saved_result, raw_text=(
        "Emisor: Nombre: PROVEEDOR DEMO RFC: AAA010101AAA\n"
        "Receptor: Nombre: COMERCIAL XXX RFC: CIA090819XXX\n"
        "Fecha: 07/08/2026\nTotal: $100.00"
    ))
    monkeypatch.setattr(TextractOcrService, "extract_expense", lambda *args, **kwargs: result)
    response = _preview(client, document_type=document_type)
    assert response.status_code == 200, response.text
    assert response.json()["extracted_total"] == "100.00"
    assert "receiver_validation" not in response.json()
    uploaded = _upload(
        client, create_expense(client, base_records), token=response.json()["verification_token"],
    )
    assert "receiver_validation" not in uploaded["ocr_extraction"]
    with session_factory() as session:
        rows = session.scalars(select(OcrExtraction)).all()
        assert len(rows) == 2
        for row in rows:
            assert row.raw_text == result.raw_text
            assert row.raw_response == RAW_RESPONSE
            if document_type == "factura":
                assert row.receiver_validation["accepted"]
                assert row.receiver_validation["fields"]["rfc"]["edit_distance"] == 3
                assert row.receiver_validation["fields"]["razon_social"]["edit_distance"] == 3
            else:
                assert row.receiver_validation is None
    headers = authenticated_audit_headers(client)
    detail = client.get(f"/api/v1/attachments/{uploaded['id']}/ocr/me", headers=headers)
    assert detail.status_code == 200, detail.text
    if document_type == "factura":
        assert detail.json()["receiver_validation"]["fields"]["rfc"]["detected"] == "CIA090819XXX"


@pytest.mark.parametrize("name,rfc,missing", [
    ("COMERCIAL IAC", "CIA09081XXXX", ["rfc"]),
    ("COMERCIA XXXX", "CIA090819PW4", ["razon_social"]),
    ("", "CIA090819PW4", ["razon_social"]),
    ("COMERCIAL IAC", "", ["rfc"]),
])
def test_rejected_receiver_keeps_same_alert_and_internal_comparison(
    client, saved_result, session_factory, monkeypatch, name, rfc, missing,
):
    result = replace(saved_result, raw_text=f"RECEPTOR\nNombre: {name}\nRFC: {rfc}")
    monkeypatch.setattr(TextractOcrService, "extract_expense", lambda *args, **kwargs: result)
    response = _preview(client)
    assert response.status_code == 409, response.text
    field_names = {"razon_social": "Raz\u00f3n Social", "rfc": "RFC"}
    assert response.json()["detail"] == {
        "code": "OCR_RECEIVER_MISMATCH",
        "message": (
            "La factura PDF no corresponde al receptor esperado.\n"
            f"Corroborar: {', '.join(field_names[field] for field in missing)}.\n"
            "Debe incluir Raz\u00f3n Social: COMERCIAL IAC y RFC: CIA090819PW4."
        ),
        "missing_fields": missing,
    }
    with session_factory() as session:
        row = session.scalars(select(OcrExtraction)).one()
        assert row.raw_text == result.raw_text
        assert row.raw_response == RAW_RESPONSE
        assert not row.receiver_validation["accepted"]
        assert row.receiver_validation["missing_fields"] == missing


def test_receiver_address_is_not_part_of_name_and_original_ocr_is_preserved(
    client, base_records, saved_result, session_factory, monkeypatch,
):
    raw_text = (
        "RECEPTOR FACTURAR A: 77750385 1814\nENTREGAR EN:\n"
        "RFC RECEPTOR CIA090819PW\nNOMBRE RECEPTOR: COMERCIAL IAC\n"
        "AV REFORMA 326 CENTRO PUEBLA DE ZARAGOZA PUEBLA MEXICO C.P.\n"
        "DOMICILIO RECEPTOR: CALLE DE PRUEBA 22\nREGIMEN FISCAL RECEPTOR: 601"
    )
    raw_response = {"Blocks": [
        {"BlockType": "LINE", "Text": line} for line in raw_text.splitlines()
    ]}
    result = replace(saved_result, raw_text=raw_text, raw_response=raw_response)
    monkeypatch.setattr(TextractOcrService, "extract_expense", lambda *args, **kwargs: result)
    response = _preview(client)
    assert response.status_code == 200, response.text
    uploaded = _upload(
        client, create_expense(client, base_records), token=response.json()["verification_token"],
    )
    with session_factory() as session:
        rows = session.scalars(select(OcrExtraction)).all()
        assert len(rows) == 2
        for row in rows:
            assert row.raw_text == raw_text
            assert row.raw_response == raw_response
            assert row.receiver_validation["accepted"]
            name = row.receiver_validation["fields"]["razon_social"]
            assert name["detected"] == "COMERCIAL IAC"
            assert name["edit_distance"] == 0
            assert row.receiver_validation["fields"]["rfc"]["edit_distance"] == 1
    detail = client.get(
        f"/api/v1/attachments/{uploaded['id']}/ocr/me", headers=authenticated_audit_headers(client),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["raw_text"] == raw_text
    assert detail.json()["receiver_validation"]["fields"]["razon_social"]["detected"] == "COMERCIAL IAC"


@pytest.mark.parametrize("raw_text", [
    (
        "PROVEEDOR DEMO\nRFC: AAA010101AAA\nFolio Fiscal: DEMO\n"
        "Numero de serie CSD del emisor: 123456\nFecha: 03/10/2026\n"
        "Facturado a: COMERCIAL IAC\nDireccion: CALLE DEMO 22\nRFC: CIA090819PW4\n"
        "Conceptos: Agua\nTotal: $100.00"
    ),
    (
        "EMISOR\nNombre: COMERCIAL IAC\nRFC: CIA090819PW4\n"
        "RECEPTOR\nNombre: OTRA EMPRESA\nRFC: OTR010101AAA"
    ),
    (
        "Nombre del receptor: COMERCIAL IAX\nRFC del receptor: OTR010101AAA\n"
        "SUBTOTAL: $100.00\nNotas: CIA090819PWX"
    ),
])
def test_global_receiver_search_is_saved_and_reused_without_changing_the_reading(
    client, base_records, saved_result, session_factory, monkeypatch, raw_text,
):
    raw_response = {"Blocks": [
        {"BlockType": "LINE", "Text": line} for line in raw_text.splitlines()
    ]}
    result = replace(saved_result, raw_text=raw_text, raw_response=raw_response)
    monkeypatch.setattr(TextractOcrService, "extract_expense", lambda *args, **kwargs: result)
    response = _preview(client, document_type="factura")
    assert response.status_code == 200, response.text
    assert "receiver_validation" not in response.json()

    def fail_if_called(*args, **kwargs):
        pytest.fail("A saved global comparison must not require another OCR reading")

    monkeypatch.setattr(TextractOcrService, "extract_expense", fail_if_called)
    uploaded = _upload(
        client, create_expense(client, base_records), token=response.json()["verification_token"],
    )
    with session_factory() as session:
        rows = session.scalars(select(OcrExtraction)).all()
        assert len(rows) == 2
        for row in rows:
            assert row.raw_text == raw_text
            assert row.raw_response == raw_response
            assert row.receiver_validation["accepted"]
            assert row.receiver_validation["scope"] == "global"
            assert row.receiver_validation["missing_fields"] == []
        assert rows[0].receiver_validation == rows[1].receiver_validation
    detail = client.get(
        f"/api/v1/attachments/{uploaded['id']}/ocr/me", headers=authenticated_audit_headers(client),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["raw_text"] == raw_text
    assert detail.json()["raw_response"] == raw_response
    assert detail.json()["receiver_validation"]["scope"] == "global"
