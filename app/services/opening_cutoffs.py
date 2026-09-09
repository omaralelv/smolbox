from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.store import Store
from app.models.store_reimbursement_opening_cutoff import (
    StoreReimbursementOpeningCutoff,
)

DEFAULT_OPENING_CUTOFF_STARTS_ON = date(2026, 7, 1)
DEFAULT_OPENING_CUTOFF_ENDS_ON = date(2026, 7, 31)
DEFAULT_OPENING_CUTOFF_AMOUNT = Decimal("0.00")
DEFAULT_OPENING_CUTOFF_NOTE = "Corte inicial antes de Smolbox."


@dataclass
class OpeningCutoffImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    missing_store_codes: list[str] = field(default_factory=list)
    processed_store_codes: list[str] = field(default_factory=list)


def ensure_opening_cutoffs_for_stores(
    db: Session,
    *,
    starts_on: date = DEFAULT_OPENING_CUTOFF_STARTS_ON,
    ends_on: date = DEFAULT_OPENING_CUTOFF_ENDS_ON,
    reimbursed_amount: Decimal = DEFAULT_OPENING_CUTOFF_AMOUNT,
    notes: str = DEFAULT_OPENING_CUTOFF_NOTE,
    store_codes: list[str] | None = None,
    update_existing: bool = False,
    allow_missing: bool = False,
) -> OpeningCutoffImportResult:
    if ends_on < starts_on:
        raise ValueError("Opening cutoff end date must be on or after start date")

    normalized_codes = _normalize_store_codes(store_codes)
    stores = _stores_for_cutoff(db, normalized_codes)
    found_codes = {_normalize_store_code(store.code) for store in stores}
    missing_codes = sorted(set(normalized_codes) - found_codes)

    if missing_codes and not allow_missing:
        raise ValueError(
            "Store codes were not found: "
            + ", ".join(missing_codes)
        )

    result = OpeningCutoffImportResult(missing_store_codes=missing_codes)

    for store in stores:
        cutoff = db.scalar(
            select(StoreReimbursementOpeningCutoff).where(
                StoreReimbursementOpeningCutoff.store_id == store.id
            )
        )

        if cutoff is None:
            db.add(
                StoreReimbursementOpeningCutoff(
                    store_id=store.id,
                    starts_on=starts_on,
                    ends_on=ends_on,
                    reimbursed_amount=reimbursed_amount,
                    notes=notes,
                )
            )
            result.created += 1
        elif update_existing:
            cutoff.starts_on = starts_on
            cutoff.ends_on = ends_on
            cutoff.reimbursed_amount = reimbursed_amount
            cutoff.notes = notes
            result.updated += 1
        else:
            result.skipped += 1

        result.processed_store_codes.append(store.code)

    db.flush()
    return result


def _stores_for_cutoff(db: Session, normalized_codes: list[str]) -> list[Store]:
    statement = select(Store).order_by(Store.code)
    if normalized_codes:
        statement = statement.where(func.upper(Store.code).in_(normalized_codes))
    return list(db.scalars(statement))


def _normalize_store_codes(store_codes: list[str] | None) -> list[str]:
    if not store_codes:
        return []

    normalized = []
    for code in store_codes:
        clean_code = _normalize_store_code(code)
        if clean_code and clean_code not in normalized:
            normalized.append(clean_code)
    return normalized


def _normalize_store_code(code: str) -> str:
    return str(code or "").strip().upper()
