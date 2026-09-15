from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.period import Period
from app.schemas.period import PeriodCreate, PeriodRead, PeriodUpdate

router = APIRouter()


@router.post("/", response_model=PeriodRead, status_code=status.HTTP_201_CREATED)
def create_period(period_in: PeriodCreate, db: Annotated[Session, Depends(get_db)]) -> Period:
    period = Period(**period_in.model_dump())
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


@router.get("/", response_model=list[PeriodRead])
def list_periods(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Period]:
    statement = select(Period).order_by(Period.starts_on.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement))


@router.get("/{period_id}", response_model=PeriodRead)
def get_period(period_id: UUID, db: Annotated[Session, Depends(get_db)]) -> Period:
    period = db.get(Period, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    return period


@router.patch("/{period_id}", response_model=PeriodRead)
def update_period(
    period_id: UUID,
    period_in: PeriodUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Period:
    period = db.get(Period, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")

    updates = period_in.model_dump(exclude_unset=True)
    starts_on = updates.get("starts_on", period.starts_on)
    ends_on = updates.get("ends_on", period.ends_on)
    if ends_on < starts_on:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="ends_on must be on or after starts_on",
        )

    for field, value in updates.items():
        setattr(period, field, value)

    db.commit()
    db.refresh(period)
    return period
