from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.store import Store
from app.models.store_reimbursement_opening_cutoff import (
    StoreReimbursementOpeningCutoff,
)


STORE_CODE = "A001"


def seed_opening_cutoff() -> None:
    db = SessionLocal()

    try:
        store = db.scalar(
            select(Store).where(
                Store.code == STORE_CODE
            )
        )

        if store is None:
            raise ValueError(
                f"No existe la tienda {STORE_CODE}."
            )

        cutoff = db.scalar(
            select(StoreReimbursementOpeningCutoff).where(
                StoreReimbursementOpeningCutoff.store_id
                == store.id
            )
        )

        if cutoff is None:
            cutoff = StoreReimbursementOpeningCutoff(
                store_id=store.id,
                starts_on=date(2026, 7, 1),
                ends_on=date(2026, 7, 31),
                reimbursed_amount=Decimal("0.00"),
                notes=(
                    "Corte inicial antes de operar "
                    "reembolsos en Smolbox."
                ),
            )
            db.add(cutoff)

        else:
            cutoff.starts_on = date(2026, 7, 1)
            cutoff.ends_on = date(2026, 7, 31)
            cutoff.reimbursed_amount = Decimal("0.00")
            cutoff.notes = (
                "Corte inicial antes de operar "
                "reembolsos en Smolbox."
            )

        db.commit()

        print(
            f"✅ Corte inicial configurado para "
            f"{STORE_CODE}."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_opening_cutoff()