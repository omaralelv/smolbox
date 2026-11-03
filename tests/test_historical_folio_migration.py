import importlib.util
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.models.historical_request import HistoricalExpense, HistoricalRequest
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store import Store
from app.models.user import User, UserRole


def test_renumbering_preserves_archive_data_normal_folios_and_audit_history(
    base_records,
    session_factory,
    monkeypatch,
):
    path = Path(__file__).parents[1] / "alembic/versions/20261103_0028_historical_folios.py"
    spec = importlib.util.spec_from_file_location("historical_folio_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    day = datetime(2026, 11, 3, 4, 30, tzinfo=UTC)  # November 2 in Mexico.
    with session_factory() as db:
        actor = User(
            email="migration@test.local",
            full_name="Test",
            password_hash="test",
            role=UserRole.admin,
        )
        other_store = Store(code="FE003", name="Otra")
        db.add_all([actor, other_store])
        db.flush()
        normal = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        normal.folio = "T001-0211202699"

        def archive(stamp, *, store_id=normal.store_id, folio=None, draft=False):
            identifier = uuid4()
            return HistoricalRequest(
                id=identifier,
                store_id=store_id,
                created_by_user_id=actor.id,
                registered_at=None if draft else stamp,
                created_at=stamp,
                status="draft" if draft else "paid",
                folio=None
                if draft
                else (
                    folio
                    or f"E-{'FE003' if store_id == other_store.id else 'T001'}-{stamp.astimezone(ZoneInfo('America/Mexico_City')):%d%m%Y}-{identifier.hex.upper()}"
                ),
            )

        legacy = [archive(day + timedelta(minutes=i)) for i in range(12)]
        another_day = archive(day + timedelta(days=1))
        another_store = archive(day, store_id=other_store.id)
        other_store.code = "FE004"  # Existing folios retain their original store code.
        unchanged = [
            archive(day, folio="E-T001-021120262"),
            archive(day, folio="E-T001-021120269"),
            archive(day, draft=True),
            archive(day, folio="CUSTOM-FOLIO"),
        ]
        records = [*legacy, another_day, another_store, *unchanged]
        db.add_all(reversed(records))
        db.flush()
        expense = HistoricalExpense(
            request_id=legacy[0].id,
            client_id=uuid4(),
            spent_on=day.date(),
            category="Agua",
            amount=Decimal("123.45"),
            document_type="vale",
        )
        original_event = AuditLog(
            action="historical_request_registered",
            message="Evento original",
            event_payload={
                "historical_request_id": str(legacy[0].id),
                "request_folio": legacy[0].folio,
            },
        )
        db.add_all([expense, original_event])
        db.commit()
        before = {row.id: row.folio for row in records}
        original_payload = dict(original_event.event_payload)
        audit_count_before = db.scalar(select(func.count()).select_from(AuditLog))
        normal_before = dict(db.execute(select(ReimbursementRequest.__table__)).mappings().one())
        expenses_before = list(db.execute(select(HistoricalExpense.__table__)).mappings())
        monkeypatch.setattr(
            migration, "op", Operations(MigrationContext.configure(db.connection()))
        )
        migration.upgrade()
        db.expire_all()
        for index, row in enumerate(legacy, start=10):
            assert row.folio == f"E-T001-02112026{index}"
            assert row.status == "paid"
        assert another_day.folio == "E-T001-031120261"
        assert another_store.folio == "E-FE003-021120261"
        assert other_store.code == "FE004"
        assert {row.id: row.folio for row in unchanged} == {
            row.id: before[row.id] for row in unchanged
        }
        assert (
            dict(db.execute(select(ReimbursementRequest.__table__)).mappings().one())
            == normal_before
        )
        assert list(db.execute(select(HistoricalExpense.__table__)).mappings()) == expenses_before
        assert original_event.event_payload == original_payload
        events = list(
            db.scalars(select(AuditLog).where(AuditLog.action == "historical_folio_updated"))
        )
        assert len(events) == 14
        assert all(
            event.reimbursement_request_id is None and event.expense_id is None for event in events
        )
        assert all(event.event_payload["previous_folio"] in before.values() for event in events)
        migration.upgrade()
        assert db.scalar(select(func.count()).select_from(AuditLog)) == audit_count_before + 14

        new_record = archive(day, folio="E-T001-0211202622")
        db.add(new_record)
        db.flush()
        migration.downgrade()
        db.expire_all()
        assert {row.id: row.folio for row in records} == before
        assert new_record.folio == "E-T001-0211202622"
        assert original_event.event_payload == original_payload
        assert db.scalar(select(func.count()).select_from(AuditLog)) == audit_count_before + 28
        migration.upgrade()
        db.expire_all()
        assert legacy[0].folio == "E-T001-0211202623"
        assert new_record.folio == "E-T001-0211202622"
