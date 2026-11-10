import importlib.util
from pathlib import Path
from uuid import UUID

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from conftest import create_expense
from sqlalchemy import inspect, text

from app.models.ocr_extraction import OcrExtraction, OcrExtractionStatus


def test_migration_preserves_attached_readings_and_prevents_loss_on_downgrade(
    client, base_records, db_engine, session_factory, monkeypatch,
):
    expense = create_expense(client, base_records)
    uploaded = client.post(
        f"/api/v1/expenses/{expense['id']}/attachments",
        files={"file": ("old.pdf", b"%PDF-1.4\ncontent\n%%EOF", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    with session_factory() as session:
        extraction = OcrExtraction(
            attachment_id=UUID(uploaded.json()["id"]), expense_id=UUID(expense["id"]),
            status=OcrExtractionStatus.succeeded, raw_text="Existing OCR text",
            raw_response={"Blocks": [{"Text": "Existing OCR text"}]},
        )
        session.add(extraction)
        session.commit()
        extraction_id = extraction.id

    path = Path(__file__).parents[1] / "alembic/versions/20261016_0024_preserve_ocr_previews.py"
    spec = importlib.util.spec_from_file_location("ocr_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    with db_engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.downgrade()
        columns = {column["name"]: column for column in inspect(connection).get_columns("ocr_extractions")}
        assert not columns["attachment_id"]["nullable"]
        assert "document_checksum_sha256" not in columns
        migration.upgrade()
        migration.upgrade()
        columns = {column["name"]: column for column in inspect(connection).get_columns("ocr_extractions")}
        assert columns["attachment_id"]["nullable"]
        assert "document_checksum_sha256" in columns
        assert "ix_ocr_extractions_document_checksum_sha256" in {
            index["name"] for index in inspect(connection).get_indexes("ocr_extractions")
        }
        assert connection.execute(text("SELECT count(*) FROM ocr_extractions")).scalar_one() == 1

    with session_factory() as session:
        old = session.get(OcrExtraction, extraction_id)
        assert old.raw_text == "Existing OCR text"
        assert old.raw_response == {"Blocks": [{"Text": "Existing OCR text"}]}
        session.add(OcrExtraction(status=OcrExtractionStatus.succeeded, raw_text="New preview"))
        session.commit()
    with db_engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        with pytest.raises(RuntimeError, match="no readings were deleted"):
            migration.downgrade()
        assert connection.execute(text("SELECT count(*) FROM ocr_extractions")).scalar_one() == 2


def test_receiver_comparison_migration_keeps_existing_raw_data(db_engine, session_factory, monkeypatch):
    with session_factory() as session:
        extraction = OcrExtraction(
            status=OcrExtractionStatus.succeeded, raw_text="COMERCIAL IAC CIA090819PW4",
            raw_response={"Blocks": [{"Text": "Original AWS text"}]},
        )
        session.add(extraction)
        session.commit()
        extraction_id = extraction.id
    path = Path(__file__).parents[1] / "alembic/versions/20261016_0025_ocr_receiver_validation.py"
    spec = importlib.util.spec_from_file_location("receiver_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with db_engine.begin() as connection:
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.downgrade()
        assert "receiver_validation" not in {
            column["name"] for column in inspect(connection).get_columns("ocr_extractions")
        }
        migration.upgrade()
        migration.upgrade()
    with session_factory() as session:
        extraction = session.get(OcrExtraction, extraction_id)
        assert extraction.raw_text == "COMERCIAL IAC CIA090819PW4"
        assert extraction.raw_response == {"Blocks": [{"Text": "Original AWS text"}]}
        assert extraction.receiver_validation is None
        extraction.receiver_validation = {"accepted": True, "max_differences": 3}
        session.commit()
    with session_factory() as session:
        assert session.get(OcrExtraction, extraction_id).receiver_validation["accepted"]
