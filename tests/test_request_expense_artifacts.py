from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.models.attachment import Attachment, AttachmentType
from app.models.audit_log import AuditActorType, AuditLog
from app.models.reimbursement_request import (
    ReimbursementRequest,
    ReimbursementRequestStatus,
)
from app.services.request_expense_artifacts import current_reimbursement_excel_attachment
from app.services.storage import StorageService


def test_editing_expense_invalidates_artifacts_and_deletes_only_tracked_reimbursement(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker,
    test_settings: Settings,
) -> None:
    expense_response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor",
            "amount": "100.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Agua",
        },
    )
    assert expense_response.status_code == 201, expense_response.text

    storage = StorageService(test_settings.upload_dir, test_settings.max_upload_bytes)
    tracked_file = storage.save_bytes(
        b"tracked reimbursement",
        filename="reembolso.xlsx",
        reimbursement_request_id=UUID(base_records["request_id"]),
    )
    unrelated_file = storage.save_bytes(
        b"unrelated request attachment",
        filename="otro.xlsx",
        reimbursement_request_id=UUID(base_records["request_id"]),
    )
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert request is not None
        tracked_attachment = Attachment(
            reimbursement_request_id=request.id,
            attachment_type=AttachmentType.cash_box_format,
            filename=tracked_file.filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            storage_path=tracked_file.storage_path,
            size_bytes=tracked_file.size_bytes,
            checksum_sha256=tracked_file.checksum_sha256,
        )
        unrelated_attachment = Attachment(
            reimbursement_request_id=request.id,
            attachment_type=AttachmentType.cash_box_format,
            filename=unrelated_file.filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            storage_path=unrelated_file.storage_path,
            size_bytes=unrelated_file.size_bytes,
            checksum_sha256=unrelated_file.checksum_sha256,
        )
        db.add_all([tracked_attachment, unrelated_attachment])
        db.flush()
        request.policy_downloaded_revision = request.expense_content_revision
        request.reimbursement_excel_revision = request.expense_content_revision
        db.add(
            AuditLog(
                reimbursement_request_id=request.id,
                actor_type=AuditActorType.system,
                action="reimbursement_excel_uploaded",
                created_at=datetime.now(UTC),
                event_payload={
                    "attachment_id": str(tracked_attachment.id),
                    "filename": tracked_file.filename,
                },
            )
        )
        db.commit()
        tracked_attachment_id = tracked_attachment.id
        unrelated_attachment_id = unrelated_attachment.id
        current_attachment = current_reimbursement_excel_attachment(db, request)
        assert current_attachment is not None
        assert current_attachment.id == tracked_attachment_id

    updated = client.patch(
        f"/api/v1/expenses/{expense_response.json()['id']}",
        json={"amount": "125.00"},
    )
    assert updated.status_code == 200, updated.text

    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert request is not None
        assert request.expense_content_revision == 2
        assert request.policy_downloaded_revision is None
        assert request.reimbursement_excel_revision is None
        assert request.artifacts_refresh_required is True
        assert db.get(Attachment, tracked_attachment_id) is None
        assert db.get(Attachment, unrelated_attachment_id) is not None

    assert not (test_settings.upload_dir / tracked_file.storage_path).exists()
    assert (test_settings.upload_dir / unrelated_file.storage_path).exists()

    created_user = client.post(
        "/api/v1/users/",
        json={
            "email": "expense-artifacts-admin@example.com",
            "full_name": "Artifacts Admin",
            "role": "admin",
            "password": "secret-password",
        },
    )
    assert created_user.status_code == 201, created_user.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "expense-artifacts-admin@example.com", "password": "secret-password"},
    )
    assert login.status_code == 200, login.text
    detail = client.get(
        f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["policyGenerated"] is False
    assert detail.json()["reimbursementCurrent"] is False
    assert detail.json()["reembolsoDownloadUrl"] is None


def test_accounting_manager_cannot_edit_expenses_during_manager_review(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker,
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor",
            "amount": "100.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Agua",
        },
    )
    assert expense.status_code == 201, expense.text
    manager = client.post(
        "/api/v1/users/",
        json={
            "email": "manager-expense-edit@example.com",
            "full_name": "Manager",
            "role": "accounting_manager",
            "password": "secret-password",
        },
    )
    assert manager.status_code == 201, manager.text
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert request is not None
        request.status = ReimbursementRequestStatus.accounting_manager_review
        db.commit()

    response = client.patch(
        f"/api/v1/expenses/{expense.json()['id']}/review",
        json={"actor_user_id": manager.json()["id"], "merchant": "Editado"},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"


def test_reimbursement_upload_is_saved_as_current_revision(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker,
    test_settings: Settings,
) -> None:
    test_settings.max_upload_bytes = 20_000
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor",
            "amount": "100.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Agua",
        },
    )
    assert expense.status_code == 201, expense.text
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert request is not None
        request.policy_downloaded_revision = request.expense_content_revision
        db.commit()

    user = client.post(
        "/api/v1/users/",
        json={
            "email": "expense-artifacts-store@example.com",
            "full_name": "Artifacts Store",
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
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "expense-artifacts-store@example.com", "password": "secret-password"},
    )
    assert login.status_code == 200, login.text

    workbook = Workbook()
    workbook.active["A1"] = "Reembolso"
    workbook_content = BytesIO()
    workbook.save(workbook_content)
    uploaded = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/reimbursement-excel/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        files={
            "file": (
                "reembolso.xlsx",
                workbook_content.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert uploaded.status_code == 201, uploaded.text

    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert request is not None
        assert request.policy_downloaded_revision == request.expense_content_revision
        assert request.reimbursement_excel_revision == request.expense_content_revision
        assert request.artifacts_refresh_required is False
        attachment = db.get(Attachment, UUID(uploaded.json()["id"]))
        assert attachment is not None
        assert (test_settings.upload_dir / attachment.storage_path).exists()


def test_manager_send_action_returns_after_artifacts_are_refreshed(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker,
) -> None:
    expense = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor",
            "amount": "100.00",
            "currency": "MXN",
            "spent_on": "2026-08-07",
            "category": "Agua",
        },
    )
    assert expense.status_code == 201, expense.text
    admin = client.post(
        "/api/v1/users/",
        json={
            "email": "expense-artifacts-workflow@example.com",
            "full_name": "Artifacts Workflow",
            "role": "admin",
            "password": "secret-password",
        },
    )
    assert admin.status_code == 201, admin.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "expense-artifacts-workflow@example.com", "password": "secret-password"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert request is not None
        request.status = ReimbursementRequestStatus.accounting_reviewed
        request.sap_policy_generated_at = datetime.now(UTC)
        request.artifacts_refresh_required = True
        db.commit()

    detail_url = f"/api/v1/frontend/solicitudes/{base_records['request_id']}/me"
    stale_detail = client.get(detail_url, headers=headers)
    assert stale_detail.status_code == 200, stale_detail.text
    assert "start_accounting_manager_review" not in stale_detail.json()["availableActions"]

    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        assert request is not None
        request.policy_downloaded_revision = request.expense_content_revision
        request.reimbursement_excel_revision = request.expense_content_revision
        request.artifacts_refresh_required = False
        db.commit()

    refreshed_detail = client.get(detail_url, headers=headers)
    assert refreshed_detail.status_code == 200, refreshed_detail.text
    assert refreshed_detail.json()["policyGenerated"] is True
    assert refreshed_detail.json()["reimbursementCurrent"] is True
    assert "start_accounting_manager_review" in refreshed_detail.json()["availableActions"]
