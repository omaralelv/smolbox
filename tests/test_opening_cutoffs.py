from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store import Store
from app.models.store_reimbursement_opening_cutoff import (
    StoreReimbursementOpeningCutoff,
)
from app.services.opening_cutoffs import ensure_opening_cutoffs_for_stores


def test_ensure_opening_cutoffs_creates_records_for_all_stores(
    session_factory,
) -> None:
    with session_factory() as db:
        db.add_all(
            [
                Store(code="A001", name="Tienda A"),
                Store(code="B002", name="Tienda B"),
            ]
        )
        db.commit()

        result = ensure_opening_cutoffs_for_stores(
            db,
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 31),
            reimbursed_amount=Decimal("0.00"),
        )
        db.commit()

        cutoffs = list(db.scalars(select(StoreReimbursementOpeningCutoff)))
        assert result.created == 2
        assert result.updated == 0
        assert result.skipped == 0
        assert len(cutoffs) == 2
        assert {cutoff.ends_on for cutoff in cutoffs} == {date(2026, 7, 31)}


def test_ensure_opening_cutoffs_skips_existing_records_by_default(
    session_factory,
) -> None:
    with session_factory() as db:
        store = Store(code="A001", name="Tienda A")
        db.add(store)
        db.flush()
        db.add(
            StoreReimbursementOpeningCutoff(
                store_id=store.id,
                starts_on=date(2026, 6, 1),
                ends_on=date(2026, 6, 30),
                reimbursed_amount=Decimal("50.00"),
            )
        )
        db.commit()

        result = ensure_opening_cutoffs_for_stores(
            db,
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 31),
            reimbursed_amount=Decimal("0.00"),
            store_codes=["A001"],
        )
        db.commit()

        cutoff = _single_cutoff(db)
        assert result.created == 0
        assert result.updated == 0
        assert result.skipped == 1
        assert cutoff.ends_on == date(2026, 6, 30)
        assert cutoff.reimbursed_amount == Decimal("50.00")


def test_ensure_opening_cutoffs_updates_existing_records_when_requested(
    session_factory,
) -> None:
    with session_factory() as db:
        store = Store(code="A001", name="Tienda A")
        db.add(store)
        db.flush()
        db.add(
            StoreReimbursementOpeningCutoff(
                store_id=store.id,
                starts_on=date(2026, 6, 1),
                ends_on=date(2026, 6, 30),
                reimbursed_amount=Decimal("50.00"),
            )
        )
        db.commit()

        result = ensure_opening_cutoffs_for_stores(
            db,
            starts_on=date(2026, 7, 1),
            ends_on=date(2026, 7, 31),
            reimbursed_amount=Decimal("0.00"),
            store_codes=["A001"],
            update_existing=True,
        )
        db.commit()

        cutoff = _single_cutoff(db)
        assert result.created == 0
        assert result.updated == 1
        assert result.skipped == 0
        assert cutoff.starts_on == date(2026, 7, 1)
        assert cutoff.ends_on == date(2026, 7, 31)
        assert cutoff.reimbursed_amount == Decimal("0.00")


def _single_cutoff(db: Session) -> StoreReimbursementOpeningCutoff:
    return db.scalar(select(StoreReimbursementOpeningCutoff))
