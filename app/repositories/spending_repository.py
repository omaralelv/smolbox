from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.models.reimbursement_request import ReimbursementRequest
from app.models.store_spending_baseline import StoreSpendingBaseline


def obtener_baseline(
    db: Session,
    store_id: UUID,
    fiscal_year: int,
) -> StoreSpendingBaseline | None:
    stmt = (
        select(StoreSpendingBaseline)
        .where(
            StoreSpendingBaseline.store_id == store_id,
            StoreSpendingBaseline.fiscal_year == fiscal_year,
        )
    )

    return db.scalar(stmt)


def obtener_gasto_aprobado_del_anio(
    db: Session,
    store_id: UUID,
    fiscal_year: int,
) -> Decimal:
    stmt = (
        select(
            func.coalesce(
                func.sum(Expense.amount),
                Decimal("0.00"),
            )
        )
        .join(
            ReimbursementRequest,
            Expense.reimbursement_request_id
            == ReimbursementRequest.id,
        )
        .where(
            ReimbursementRequest.store_id == store_id,
            ReimbursementRequest.status.in_(
                ["paid", "direction_approved"]
            ),
            Expense.removed_at.is_(None),
            func.extract(
                "year",
                Expense.spent_on,
            ) == fiscal_year,
        )
    )

    return db.scalar(stmt) or Decimal("0.00")