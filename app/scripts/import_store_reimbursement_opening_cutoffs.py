from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation

from app.db.session import SessionLocal
from app.services.opening_cutoffs import (
    DEFAULT_OPENING_CUTOFF_AMOUNT,
    DEFAULT_OPENING_CUTOFF_ENDS_ON,
    DEFAULT_OPENING_CUTOFF_NOTE,
    DEFAULT_OPENING_CUTOFF_STARTS_ON,
    ensure_opening_cutoffs_for_stores,
)


def main() -> None:
    args = _parse_args()
    db = SessionLocal()

    try:
        result = ensure_opening_cutoffs_for_stores(
            db,
            starts_on=args.starts_on,
            ends_on=args.ends_on,
            reimbursed_amount=args.amount,
            notes=args.notes,
            store_codes=args.store_code,
            update_existing=args.update_existing,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Cortes iniciales procesados.")
    print(f"Creados: {result.created}")
    print(f"Actualizados: {result.updated}")
    print(f"Existentes sin cambio: {result.skipped}")
    print(f"Tiendas procesadas: {len(result.processed_store_codes)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create store reimbursement opening cutoffs."
    )
    parser.add_argument(
        "--starts-on",
        type=_parse_date,
        default=DEFAULT_OPENING_CUTOFF_STARTS_ON,
        help="Opening cutoff start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--ends-on",
        type=_parse_date,
        default=DEFAULT_OPENING_CUTOFF_ENDS_ON,
        help="Opening cutoff end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--amount",
        type=_parse_decimal,
        default=DEFAULT_OPENING_CUTOFF_AMOUNT,
        help="Amount reimbursed before Smolbox. Default: 0.00.",
    )
    parser.add_argument(
        "--notes",
        default=DEFAULT_OPENING_CUTOFF_NOTE,
        help="Notes saved on the opening cutoff records.",
    )
    parser.add_argument(
        "--store-code",
        action="append",
        help="Store code to process. Repeat for multiple stores. Omit to process all stores.",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update existing opening cutoffs instead of leaving them unchanged.",
    )
    return parser.parse_args()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Date must use YYYY-MM-DD format"
        ) from exc


def _parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise argparse.ArgumentTypeError("Amount must be numeric") from exc


if __name__ == "__main__":
    main()
