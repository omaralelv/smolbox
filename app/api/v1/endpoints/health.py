import os
from hashlib import sha256
from pathlib import Path
from typing import Annotated

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
    version: str


@router.get("/health", response_model=HealthResponse)
def health(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    database_status = "ok"
    status = "ok"
    try:
        db.execute(text("select 1"))
    except SQLAlchemyError:
        database_status = "unavailable"
        status = "degraded"

    return HealthResponse(status=status, database=database_status, version=_application_version())


def _application_version() -> str:
    explicit_version = (
        os.getenv("SMOLBOX_APP_VERSION")
        or os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("COMMIT_SHA")
    )
    if explicit_version:
        return explicit_version.strip()[:40]

    app_root = Path(__file__).resolve().parents[3]
    repository_root = app_root.parent
    files_to_hash = [
        *app_root.rglob("*.py"),
        *repository_root.glob("pyproject.toml"),
        *repository_root.glob("frontend/package.json"),
        *repository_root.glob("frontend/vite.config.js"),
        *repository_root.glob("frontend/src/**/*.jsx"),
        *repository_root.glob("frontend/src/**/*.js"),
        *repository_root.glob("frontend/src/**/*.css"),
    ]

    digest = sha256()
    for path in sorted({path for path in files_to_hash if path.is_file()}):
        relative_path = path.relative_to(repository_root)
        if "__pycache__" in relative_path.parts:
            continue
        digest.update(str(relative_path).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")

    return digest.hexdigest()[:16]
