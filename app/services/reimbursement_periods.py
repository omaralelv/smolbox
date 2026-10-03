from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

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
    statement = (
        select(ReimbursementRequest)
        .where(
            ReimbursementRequest.store_id == store_id,
            ReimbursementRequest.reimbursement_starts_on.is_not(None),
            ReimbursementRequest.reimbursement_ends_on.is_not(None),

            ReimbursementRequest.status.not_in(
                {
                    ReimbursementRequestStatus.draft,
                    ReimbursementRequestStatus.rejected,
                }
            ),
        )
        .order_by(
            ReimbursementRequest.reimbursement_ends_on.desc(),
            ReimbursementRequest.created_at.desc(),
        )
    )

    if exclude_request_id is not None:
        statement = statement.where(
            ReimbursementRequest.id != exclude_request_id
        )

    return db.scalar(statement.limit(1))


def obtener_contexto_periodo_reembolso(
    db: Session,
    store_id: UUID,
    *,
    fecha_fin_actual: date,
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
        misma_fecha_del_folio = (
            solicitud_anterior.reimbursement_ends_on == fecha_fin_actual
        )
        inicio_actual = (
            solicitud_anterior.reimbursement_starts_on
            if misma_fecha_del_folio
            else solicitud_anterior.reimbursement_ends_on + timedelta(days=1)
        )

        if not misma_fecha_del_folio and fecha_fin_actual < inicio_actual:
            raise ValueError(
                "La fecha final del reembolso no puede ser "
                "anterior al inicio calculado desde la "
                "solicitud previa."
            )

        return ReimbursementPeriodContext(
            current_starts_on=inicio_actual,
            previous_starts_on=(
                solicitud_anterior.reimbursement_starts_on
            ),
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

    if fecha_fin_actual < inicio_actual:
        raise ValueError(
            "La fecha final no puede ser anterior al corte "
            "inicial de la tienda."
        )

    return ReimbursementPeriodContext(
        current_starts_on=inicio_actual,
        previous_starts_on=corte_inicial.starts_on,
        previous_ends_on=corte_inicial.ends_on,
        previous_amount=corte_inicial.reimbursed_amount,
        previous_request_id=None,
        source="opening_cutoff",
    )