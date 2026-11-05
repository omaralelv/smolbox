import importlib.util
from io import StringIO
from pathlib import Path
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_migration_adds_only_archive_tables_and_preserves_existing_data(monkeypatch):
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    for name in ("stores", "users", "periods", "reimbursement_requests"):
        sa.Table(name, metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)
    path = Path(__file__).parents[1] / "alembic/versions/20261103_0027_historical_requests.py"
    spec = importlib.util.spec_from_file_location("historical_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        before = set(sa.inspect(connection).get_table_names())
        for table in metadata.tables.values():
            connection.execute(table.insert().values(id=uuid4()))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        inspector = sa.inspect(connection)
        added = set(inspector.get_table_names()) - before
        assert added == {"historical_requests", "historical_expenses", "historical_attachments"}
        assert {
            key["referred_table"] for key in inspector.get_foreign_keys("historical_requests")
        } == {"stores", "users"}
        assert all(
            key["referred_table"] not in {"periods", "reimbursement_requests"}
            for table in added
            for key in inspector.get_foreign_keys(table)
        )
        indexes = {index["name"] for index in inspector.get_indexes("historical_requests")}
        assert "uq_historical_open_draft" in indexes
        for table in metadata.tables.values():
            assert connection.scalar(sa.select(sa.func.count()).select_from(table)) == 1
        migration.downgrade()
        assert set(sa.inspect(connection).get_table_names()) == before
    engine.dispose()


def test_migration_compiles_postgres_ddl_without_altering_operational_tables(monkeypatch):
    path = Path(__file__).parents[1] / "alembic/versions/20261103_0027_historical_requests.py"
    spec = importlib.util.spec_from_file_location("historical_migration_pg", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    monkeypatch.setattr(migration, "op", Operations(context))
    migration.upgrade()
    sql = output.getvalue()
    assert "CREATE TABLE historical_requests" in sql
    assert "WHERE status = 'draft'" in sql
    assert "WHERE removed_at IS NULL AND cfdi_uuid IS NOT NULL" in sql
    assert "ALTER TABLE" not in sql and "UPDATE reimbursement_requests" not in sql
