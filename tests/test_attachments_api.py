from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from conftest import create_expense
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_db


def _xlsx_bytes() -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "<Types />")
        workbook.writestr("xl/workbook.xml", "<workbook />")
    return output.getvalue()


def test_accepts_real_xlsx_and_rejects_fake_pdf(
    client: TestClient,
    base_records: dict[str, str],
    test_settings: Settings,
) -> None:
    xlsx = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/attachments",
        data={"attachment_type": "cash_box_format"},
        files={
            "file": (
                "caja-chica.xlsx",
                _xlsx_bytes(),
                "application/octet-stream",
            )
        },
    )
    assert xlsx.status_code == 201, xlsx.text
    assert (
        xlsx.json()["content_type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "storage_path" not in xlsx.json()

    expense = create_expense(client, base_records)
    fake_pdf = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"not a pdf", "application/pdf")},
    )
    assert fake_pdf.status_code == 415

    stored_files = [path for path in test_settings.upload_dir.rglob("*") if path.is_file()]
    assert len(stored_files) == 1


def test_attachment_download_returns_file_or_404(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records)
    uploaded = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text

    downloaded = client.get(f"/api/v1/attachments/{uploaded.json()['id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF-1.4")
    assert downloaded.headers["content-type"] == "application/pdf"

    missing = client.get(f"/api/v1/attachments/{uuid4()}/download")
    assert missing.status_code == 404


def test_authenticated_attachment_download_requires_store_scope(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    expense = create_expense(client, base_records)
    uploaded = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        data={"attachment_type": "receipt"},
        files={"file": ("receipt.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text

    assigned_user = client.post(
        "/api/v1/users/",
        json={
            "email": "attachment.store@example.com",
            "full_name": "Attachment Store",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert assigned_user.status_code == 201, assigned_user.text
    assignment = client.post(
        f"/api/v1/stores/{base_records['store_id']}/users",
        json={"user_id": assigned_user.json()["id"], "role": "store"},
    )
    assert assignment.status_code == 201, assignment.text

    unassigned_user = client.post(
        "/api/v1/users/",
        json={
            "email": "attachment.unassigned@example.com",
            "full_name": "Attachment Unassigned",
            "role": "store",
            "password": "secret-password",
        },
    )
    assert unassigned_user.status_code == 201, unassigned_user.text

    assigned_token = client.post(
        "/api/v1/auth/login",
        json={"email": "attachment.store@example.com", "password": "secret-password"},
    )
    assert assigned_token.status_code == 200, assigned_token.text
    protected = client.get(
        f"/api/v1/attachments/{uploaded.json()['id']}/download/me",
        headers={"Authorization": f"Bearer {assigned_token.json()['access_token']}"},
    )
    assert protected.status_code == 200, protected.text
    assert protected.content.startswith(b"%PDF-1.4")

    unassigned_token = client.post(
        "/api/v1/auth/login",
        json={"email": "attachment.unassigned@example.com", "password": "secret-password"},
    )
    assert unassigned_token.status_code == 200, unassigned_token.text
    blocked = client.get(
        f"/api/v1/attachments/{uploaded.json()['id']}/download/me",
        headers={"Authorization": f"Bearer {unassigned_token.json()['access_token']}"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "STORE_ASSIGNMENT_REQUIRED"


def test_database_failure_does_not_leave_orphan_file(
    test_app: FastAPI,
    db_engine: Engine,
    base_records: dict[str, str],
    client: TestClient,
    test_settings: Settings,
) -> None:
    expense = create_expense(client, base_records)
    failing_session = Session(db_engine)

    def fail_commit(session: Session) -> None:
        raise RuntimeError("forced database failure")

    event.listen(failing_session, "before_commit", fail_commit)

    def override_failing_db():
        try:
            yield failing_session
        finally:
            failing_session.close()

    original_override = test_app.dependency_overrides[get_db]
    test_app.dependency_overrides[get_db] = override_failing_db
    try:
        with TestClient(test_app, raise_server_exceptions=False) as failing_client:
            response = failing_client.post(
                f"/api/v1/expenses/{expense['id']}/attachments",
                data={"attachment_type": "receipt"},
                files={
                    "file": (
                        "receipt.pdf",
                        b"%PDF-1.4\ncontent\n%%EOF",
                        "application/pdf",
                    )
                },
            )
        assert response.status_code == 500
    finally:
        test_app.dependency_overrides[get_db] = original_override

    owner_directory = test_settings.upload_dir / str(expense["id"])
    assert not owner_directory.exists() or not any(Path(owner_directory).iterdir())
