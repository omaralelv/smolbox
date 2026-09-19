import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=os.getenv(
            "SMOLBOX_TEST_DATABASE_URL",
            f"sqlite+pysqlite:///{tmp_path / 'smolbox-test.db'}",
        ),
        upload_dir=tmp_path / "uploads",
        max_upload_bytes=4096,
        cfdi_receiver_rfc="BBB010101BBB",
    )


@pytest.fixture
def db_engine(test_settings: Settings) -> Generator[Engine, None, None]:
    connect_args = (
        {"check_same_thread": False} if test_settings.database_url.startswith("sqlite") else {}
    )
    engine = create_engine(test_settings.database_url, connect_args=connect_args)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def session_factory(db_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def test_app(
    session_factory: sessionmaker[Session],
    test_settings: Settings,
) -> Generator[FastAPI, None, None]:
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(test_app) as test_client:
        yield test_client


@pytest.fixture
def base_records(client: TestClient) -> dict[str, str]:
    store = client.post(
        "/api/v1/stores/",
        json={"code": "T001", "name": "Tienda Centro"},
    )
    assert store.status_code == 201, store.text

    period = client.post(
        "/api/v1/periods/",
        json={
            "name": "Agosto 2026",
            "starts_on": "2026-08-01",
            "ends_on": "2026-08-31",
        },
    )
    assert period.status_code == 201, period.text

    request = client.post(
        "/api/v1/reimbursement-requests/",
        json={
            "store_id": store.json()["id"],
            "period_id": period.json()["id"],
            "reported_total": "1500.00",
        },
    )
    assert request.status_code == 201, request.text
    return {
        "store_id": store.json()["id"],
        "period_id": period.json()["id"],
        "request_id": request.json()["id"],
    }


def create_expense(
    client: TestClient,
    base_records: dict[str, str],
    *,
    amount: str = "123.45",
    spent_on: str = "2026-08-07",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/expenses/",
        json={
            "reimbursement_request_id": base_records["request_id"],
            "merchant": "Proveedor Demo",
            "amount": amount,
            "currency": "MXN",
            "spent_on": spent_on,
            "category": "papeleria",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
