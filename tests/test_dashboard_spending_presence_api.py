from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from conftest import authenticated_audit_headers
from sqlalchemy import select

from app.models.expense import Expense, ExpenseStatus
from app.models.historical_request import HistoricalExpense, HistoricalRequest
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.store import Store
from app.models.store_spending_baseline import StoreSpendingBaseline
from app.models.user import User

URL = "/api/v1/frontend/tesoreria/dashboard/me"


def test_dashboard_presence_uses_records_not_amounts_and_respects_the_existing_spending_window(
    client,
    base_records,
    session_factory,
):
    headers = authenticated_audit_headers(client)
    years = client.get(URL, headers=headers).json()["years"]
    oldest, previous, current = years
    now = datetime.now(UTC)
    with session_factory() as db:
        actor = db.scalar(select(User).where(User.email == "audit-reader@example.com"))
        stores = {
            name: Store(code=f"X{index:03}", name=name)
            for index, name in enumerate(
                [
                    "archive_only",
                    "zero_baseline",
                    "zero_normal",
                    "zero_archive",
                    "empty",
                    "excluded_normal",
                    "excluded_archive",
                    "mixed",
                ],
                start=1,
            )
        }
        db.add_all(stores.values())
        db.flush()

        def normal(
            store_id,
            amount,
            year,
            *,
            request_status=ReimbursementRequestStatus.paid,
            expense_status=ExpenseStatus.approved,
            removed=False,
        ):
            request = ReimbursementRequest(
                store_id=store_id, period_id=UUID(base_records["period_id"]), status=request_status
            )
            db.add(request)
            db.flush()
            db.add(
                Expense(
                    reimbursement_request_id=request.id,
                    period_id=request.period_id,
                    merchant="Normal",
                    amount=Decimal(amount),
                    spent_on=date(year, 1, 15),
                    status=expense_status,
                    removed_at=now if removed else None,
                )
            )

        def archived(name, amount, year, *, draft=False, removed=False):
            request = HistoricalRequest(
                store_id=stores[name].id,
                created_by_user_id=actor.id,
                status="draft" if draft else "paid",
                registered_at=None if draft else now,
                folio=None if draft else f"E-TEST-{uuid4().hex}",
            )
            db.add(request)
            db.flush()
            db.add(
                HistoricalExpense(
                    request_id=request.id,
                    client_id=uuid4(),
                    spent_on=date(year, 1, 15),
                    category="Agua",
                    amount=Decimal(amount),
                    document_type="vale",
                    removed_at=now if removed else None,
                )
            )

        normal(UUID(base_records["store_id"]), "100", current)
        normal(stores["zero_normal"].id, "0", current)
        archived("archive_only", "20", previous)
        archived("zero_archive", "0", oldest)
        for name, amount, year in [
            ("zero_baseline", "0", oldest),
            ("empty", "999", oldest - 1),
            ("mixed", "75", oldest),
        ]:
            db.add(
                StoreSpendingBaseline(
                    store_id=stores[name].id,
                    fiscal_year=year,
                    historical_amount=Decimal(amount),
                    baseline_as_of=date(year, 1, 1),
                )
            )
        normal(stores["mixed"].id, "0", current)
        archived("mixed", "25", current)
        normal(stores["excluded_normal"].id, "500", current, removed=True)
        normal(stores["excluded_normal"].id, "500", current, expense_status=ExpenseStatus.rejected)
        normal(
            stores["excluded_normal"].id,
            "500",
            current,
            request_status=ReimbursementRequestStatus.draft,
        )
        normal(stores["excluded_normal"].id, "500", oldest - 1)
        archived("excluded_archive", "500", current, removed=True)
        archived("excluded_archive", "500", current, draft=True)
        archived("excluded_archive", "500", oldest - 1)
        db.commit()
        expected = {
            str(stores[name].id): flags
            for name, flags in {
                "archive_only": (False, True),
                "zero_baseline": (True, False),
                "zero_normal": (True, False),
                "zero_archive": (False, True),
                "empty": (False, False),
                "excluded_normal": (False, False),
                "excluded_archive": (False, False),
                "mixed": (True, True),
            }.items()
        }
        expected[base_records["store_id"]] = (True, False)
        before = list(db.execute(select(ReimbursementRequest.__table__)).mappings())

    response = client.get(URL, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert {row["id"] for row in data["stores"]} == set(
        expected
    )  # Keep the store catalog available.
    assert {
        row["storeId"]: (row["hasNormalData"], row["hasExtemporaneousData"]) for row in data["rows"]
    } == expected
    for row in data["rows"]:
        for year in map(str, years):
            assert (
                row["values"][year] == row["normalValues"][year] + row["extemporaneousValues"][year]
            )
        if row["storeName"].startswith("zero_") or not any(expected[row["storeId"]]):
            assert all(value == 0 for value in row["values"].values())
    assert {year: sum(row["values"][str(year)] for row in data["rows"]) for year in years} == {
        oldest: 75,
        previous: 20,
        current: 125,
    }
    with session_factory() as db:
        assert list(db.execute(select(ReimbursementRequest.__table__)).mappings()) == before


@pytest.mark.parametrize(
    "role,allowed",
    [
        ("admin", True),
        ("accountant", True),
        ("accounting_manager", True),
        ("treasury", True),
        ("director", True),
        ("store", False),
        ("authorizer", False),
    ],
)
def test_dashboard_presence_keeps_existing_role_permissions(client, role, allowed):
    email = f"dashboard-{role}@test.local"
    created = client.post(
        "/api/v1/users/",
        json={
            "email": email,
            "full_name": role,
            "role": role,
            "password": "secret-password",
        },
    )
    assert created.status_code == 201, created.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secret-password"})
    assert login.status_code == 200, login.text
    response = client.get(URL, headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert response.status_code == (200 if allowed else 403), response.text
    if allowed:
        assert all(
            isinstance(row["hasNormalData"], bool)
            and isinstance(row["hasExtemporaneousData"], bool)
            for row in response.json()["rows"]
        )
