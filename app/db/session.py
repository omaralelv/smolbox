from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

# Import models so SQLAlchemy metadata contains every table before create_all.
from app.models import (  # noqa: F401
    attachment,
    audit_log,
    business_rule,
    cfdi_validation,
    expense,
    payment,
    period,
    reimbursement_request,
    store,
    user,
)

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_database_schema() -> None:
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
