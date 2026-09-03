from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.spending_repository import (
    obtener_baseline,
    obtener_gasto_aprobado_posterior_al_baseline,
)


def obtener_resumen_gasto_tienda(
    db: Session,
    store_id: UUID,
    fiscal_year: int,
) -> dict:
    baseline = obtener_baseline(
        db=db,
        store_id=store_id,
        fiscal_year=fiscal_year,
    )

    if baseline is None:
        return {
            "store_id": str(store_id),
            "fiscal_year": fiscal_year,
            "historical_amount": Decimal("0.00"),
            "new_approved_amount": Decimal("0.00"),
            "current_accumulated": Decimal("0.00"),
            "baseline_as_of": None,
        }

    gasto_nuevo = (
        obtener_gasto_aprobado_posterior_al_baseline(
            db=db,
            store_id=store_id,
            fiscal_year=fiscal_year,
            baseline_as_of=baseline.baseline_as_of,
        )
    )

    acumulado_actual = (
        baseline.historical_amount + gasto_nuevo
    )

    return {
        "store_id": str(store_id),
        "fiscal_year": fiscal_year,
        "historical_amount": baseline.historical_amount,
        "new_approved_amount": gasto_nuevo,
        "current_accumulated": acumulado_actual,
        "baseline_as_of": baseline.baseline_as_of,
    }