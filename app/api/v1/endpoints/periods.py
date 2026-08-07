from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.period import Period
from app.schemas.period import PeriodCreate, PeriodRead


router = APIRouter()


@router.post("/", response_model=PeriodRead, status_code=status.HTTP_201_CREATED)
def create_period(period_in: PeriodCreate, db: Session = Depends(get_db)) -> Period:
    period = Period(**period_in.model_dump())
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


@router.get("/", response_model=list[PeriodRead])
def list_periods(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Period]:
    statement = select(Period).order_by(Period.starts_on.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement))


@router.get("/{period_id}", response_model=PeriodRead)
def get_period(period_id: UUID, db: Session = Depends(get_db)) -> Period:
    period = db.get(Period, period_id)
    if period is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Period not found")
    return period
