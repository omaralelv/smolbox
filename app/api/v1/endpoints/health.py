from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    database_status = "ok"
    status = "ok"
    try:
        db.execute(text("select 1"))
    except SQLAlchemyError:
        database_status = "unavailable"
        status = "degraded"

    return HealthResponse(status=status, database=database_status)
