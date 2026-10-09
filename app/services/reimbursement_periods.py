from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseStatus
from app.models.reimbursement_request import (
    ReimbursementRequest,
    ReimbursementRequestStatus,
)
from app.models.store_reimbursement_opening_cutoff import (
    StoreReimbursementOpeningCutoff,
)


@dataclass
class ReimbursementPeriodContext:
    current_starts_on: date
    previous_starts_on: date | None
    previous_ends_on: date | None
    previous_amount: Decimal
    previous_request_id: UUID | None
    source: str


class ExpenseOutsideReimbursementPeriod(ValueError):
    pass


class ReimbursementPeriodBoundaryUnavailable(ValueError):
    pass


def _active_expense_filters():
    return (
        Expense.removed_at.is_(None),
        Expense.status.not_in(
            {ExpenseStatus.removed, ExpenseStatus.rejected}
        ),
    )


def obtener_ultima_fecha_gasto_reembolso(
    db: Session,
    request_id: UUID,
) -> date | None:
    return db.scalar(
        select(func.max(Expense.spent_on)).where(
            Expense.reimbursement_request_id == request_id,
            *_active_expense_filters(),
        )
    )


def actualizar_fecha_fin_reembolso(
    db: Session,
    solicitud: ReimbursementRequest,
) -> date | None:
    db.flush()
    ultima_fecha_gasto = obtener_ultima_fecha_gasto_reembolso(
        db,
        solicitud.id,
    )
    solicitud.reimbursement_ends_on = (
        ultima_fecha_gasto
        if ultima_fecha_gasto is not None
        and (
            solicitud.reimbursement_starts_on is None
            or ultima_fecha_gasto >= solicitud.reimbursement_starts_on
        )
        else None
    )
    return solicitud.reimbursement_ends_on


def _inicio_solicitud_desde_gastos(
    db: Session,
    solicitud: ReimbursementRequest,
) -> date | None:
    if solicitud.previous_reimbursement_request_id is not None:
        fecha_fin_anterior = obtener_ultima_fecha_gasto_reembolso(
            db,
            solicitud.previous_reimbursement_request_id,
        )
    else:
        fecha_fin_anterior = solicitud.previous_reimbursement_ends_on
        if fecha_fin_anterior is None:
            corte_inicial = db.scalar(
                select(StoreReimbursementOpeningCutoff).where(
                    StoreReimbursementOpeningCutoff.store_id
                    == solicitud.store_id
                )
            )
            fecha_fin_anterior = (
                corte_inicial.ends_on
                if corte_inicial is not None
                else None
            )

    return (
        fecha_fin_anterior + timedelta(days=1)
        if fecha_fin_anterior is not None
        else None
    )


def obtener_inicio_periodo_reembolso(
    db: Session,
    request_id: UUID,
) -> date | None:
    solicitud = db.get(ReimbursementRequest, request_id)
    if solicitud is None:
        raise ValueError("No se encontró la solicitud anterior del reembolso.")

    inicio = _inicio_solicitud_desde_gastos(db, solicitud)
    if inicio is not None:
        solicitud.reimbursement_starts_on = inicio
    return inicio


def validate_expense_date_for_reimbursement(
    spent_on: date | datetime,
    *,
    previous_ends_on: date | None,
) -> None:
    if previous_ends_on is None:
        raise ReimbursementPeriodBoundaryUnavailable
    expense_date = spent_on.date() if isinstance(spent_on, datetime) else spent_on
    if expense_date < previous_ends_on:
        raise ExpenseOutsideReimbursementPeriod


def obtener_ultima_solicitud_con_periodo(
    db: Session,
    store_id: UUID,
    *,
    exclude_request_id: UUID | None = None,
) -> ReimbursementRequest | None:
    ultima_fecha_gasto = func.max(Expense.spent_on).label(
        "ultima_fecha_gasto"
    )
    statement = (
        select(ReimbursementRequest, ultima_fecha_gasto)
        .join(
            Expense,
            Expense.reimbursement_request_id
            == ReimbursementRequest.id,
        )
        .where(
            ReimbursementRequest.store_id == store_id,
            ReimbursementRequest.status.not_in(
                {
                    ReimbursementRequestStatus.draft,
                    ReimbursementRequestStatus.rejected,
                }
            ),
            *_active_expense_filters(),
        )
        .group_by(ReimbursementRequest.id)
        .order_by(
            ultima_fecha_gasto.desc(),
            ReimbursementRequest.created_at.desc(),
        )
    )

    if exclude_request_id is not None:
        statement = statement.where(
            ReimbursementRequest.id != exclude_request_id
        )

    row = db.execute(statement.limit(1)).first()
    if row is None:
        return None

    solicitud_anterior, ultima_fecha = row
    solicitud_anterior.reimbursement_ends_on = ultima_fecha
    return solicitud_anterior


def obtener_contexto_periodo_reembolso(
    db: Session,
    store_id: UUID,
    *,
    exclude_request_id: UUID | None = None,
) -> ReimbursementPeriodContext:
    solicitud_anterior = (
        obtener_ultima_solicitud_con_periodo(
            db=db,
            store_id=store_id,
            exclude_request_id=exclude_request_id,
        )
    )

    if solicitud_anterior is not None:
        inicio_solicitud_anterior = _inicio_solicitud_desde_gastos(
            db,
            solicitud_anterior,
        )
        if inicio_solicitud_anterior is not None:
            solicitud_anterior.reimbursement_starts_on = (
                inicio_solicitud_anterior
            )
        inicio_actual = solicitud_anterior.reimbursement_ends_on + timedelta(days=1)

        return ReimbursementPeriodContext(
            current_starts_on=inicio_actual,
            previous_starts_on=inicio_solicitud_anterior,
            previous_ends_on=(
                solicitud_anterior.reimbursement_ends_on
            ),
            previous_amount=(
                solicitud_anterior.reported_total
                or Decimal("0.00")
            ),
            previous_request_id=solicitud_anterior.id,
            source="previous_request",
        )

    corte_inicial = db.scalar(
        select(StoreReimbursementOpeningCutoff).where(
            StoreReimbursementOpeningCutoff.store_id
            == store_id
        )
    )

    if corte_inicial is None:
        raise ValueError(
            "La tienda no tiene una solicitud anterior ni "
            "un corte inicial configurado. Configura primero "
            "su historial de caja chica."
        )

    inicio_actual = corte_inicial.ends_on + timedelta(days=1)

    return ReimbursementPeriodContext(
        current_starts_on=inicio_actual,
        previous_starts_on=corte_inicial.starts_on,
        previous_ends_on=corte_inicial.ends_on,
        previous_amount=corte_inicial.reimbursed_amount,
        previous_request_id=None,
        source="opening_cutoff",
    )