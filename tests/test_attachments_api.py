from io import BytesIO
from pathlib import Path
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
