import importlib.util
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _legacy_date(day):
    return datetime.fromisoformat(f"2026-10-{day:02d}T00:00:00")


def test_age_migration_backfills_only_proven_events_and_keeps_existing_data(monkeypatch):
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    requests = sa.Table(
        "reimbursement_requests", metadata, sa.Column("id", sa.String, primary_key=True),
        sa.Column("submitted_at", sa.DateTime), sa.Column("notes", sa.String),
    )
    events = sa.Table(
        "audit_logs", metadata, sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reimbursement_request_id", sa.String), sa.Column("action", sa.String),
        sa.Column("to_status", sa.String), sa.Column("created_at", sa.DateTime),
    )
    metadata.create_all(engine)
    path = Path(__file__).parents[1] / "alembic/versions/20261028_0026_request_age.py"
    spec = importlib.util.spec_from_file_location("age_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        connection.execute(requests.insert(), [
            {"id": "with-history", "submitted_at": _legacy_date(26), "notes": "Keep me"},
            {"id": "unknown", "submitted_at": _legacy_date(21), "notes": "No audit evidence"},
        ])
        connection.execute(events.insert(), [
            {"reimbursement_request_id": "with-history", "action": action, "to_status": status,
             "created_at": _legacy_date(day)}
            for action, status, day in [
                ("button_selected", "submitted", 19),
                ("request_status_changed", "submitted", 20),
                ("request_status_changed", "submitted", 26),
                ("request_status_changed", "rejected", 27),
                ("expense_authorization_rejected", "rejected", 18),
            ]
        ])
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        migration.upgrade()
        upgraded = sa.Table("reimbursement_requests", sa.MetaData(), autoload_with=connection)
        rows = {row.id: row for row in connection.execute(sa.select(upgraded))}
        assert rows["with-history"].first_submitted_at == _legacy_date(20)
        assert rows["with-history"].submitted_at == _legacy_date(26)
        assert rows["with-history"].rejected_at == _legacy_date(27)
        assert rows["with-history"].notes == "Keep me"
        assert rows["unknown"].first_submitted_at is None
        assert rows["unknown"].rejected_at is None
        connection.execute(upgraded.update().where(upgraded.c.id == "with-history")
                           .values(first_submitted_at=_legacy_date(17)))
        migration.upgrade()
        assert connection.scalar(sa.select(upgraded.c.first_submitted_at).where(
            upgraded.c.id == "with-history",
        )) == _legacy_date(17)
        migration.downgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("reimbursement_requests")}
        assert "first_submitted_at" not in columns
        assert "rejected_at" not in columns
        assert connection.scalar(sa.select(sa.func.count()).select_from(requests)) == 2
        assert connection.scalar(sa.select(sa.func.count()).select_from(events)) == 5
    engine.dispose()
