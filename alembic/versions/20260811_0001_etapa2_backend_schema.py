"""Etapa 2 backend schema.

Revision ID: 20260811_0001
Revises:
Create Date: 2026-08-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.db.base import Base
from app.models import (  # noqa: F401
    attachment,
    audit_log,
    cfdi_validation,
    expense,
    period,
    reimbursement_request,
    store,
    user,
)

revision: str = "20260811_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_reimbursement_status_values(bind)
    _ensure_stage2_enum_types(bind)
    Base.metadata.create_all(bind=bind)
    _upgrade_existing_reimbursement_requests(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _drop_column_if_exists(bind, "reimbursement_requests", "closed_at")
    _drop_column_if_exists(bind, "reimbursement_requests", "paid_at")
    _drop_column_if_exists(bind, "reimbursement_requests", "approved_for_payment_at")
    _drop_column_if_exists(bind, "reimbursement_requests", "treasury_reviewed_at")
    _drop_column_if_exists(bind, "reimbursement_requests", "accounting_reviewed_at")
    _drop_column_if_exists(bind, "reimbursement_requests", "submitted_at")
    Base.metadata.tables["audit_logs"].drop(bind=bind, checkfirst=True)
    Base.metadata.tables["users"].drop(bind=bind, checkfirst=True)

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="audit_actor_type").drop(bind, checkfirst=True)
        postgresql.ENUM(name="user_role").drop(bind, checkfirst=True)


def _upgrade_existing_reimbursement_requests(bind) -> None:
    if not _has_table(bind, "reimbursement_requests"):
        return

    timestamp = sa.DateTime(timezone=True)
    _add_column_if_missing(bind, "reimbursement_requests", sa.Column("submitted_at", timestamp))
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("accounting_reviewed_at", timestamp),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("treasury_reviewed_at", timestamp),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("approved_for_payment_at", timestamp),
    )
    _add_column_if_missing(bind, "reimbursement_requests", sa.Column("paid_at", timestamp))
    _add_column_if_missing(bind, "reimbursement_requests", sa.Column("closed_at", timestamp))


def _ensure_reimbursement_status_values(bind) -> None:
    if bind.dialect.name != "postgresql" or not _has_pg_enum(bind, "reimbursement_request_status"):
        return

    for value in [
        "treasury_review",
        "approved_for_payment",
        "paid",
        "rejected",
    ]:
        op.execute(f"ALTER TYPE reimbursement_request_status ADD VALUE IF NOT EXISTS '{value}'")


def _ensure_stage2_enum_types(bind) -> None:
    if bind.dialect.name != "postgresql":
        return

    postgresql.ENUM(
        "store",
        "accountant",
        "treasury",
        "admin",
        name="user_role",
    ).create(bind, checkfirst=True)
    postgresql.ENUM(
        "system",
        "user",
        name="audit_actor_type",
    ).create(bind, checkfirst=True)


def _has_pg_enum(bind, name: str) -> bool:
    result = bind.execute(
        sa.text("select 1 from pg_type where typname = :name"),
        {"name": name},
    )
    return result.scalar() is not None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return column_name in {
        column["name"] for column in sa.inspect(bind).get_columns(table_name)
    }


def _add_column_if_missing(bind, table_name: str, column: sa.Column) -> None:
    if not _has_column(bind, table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(bind, table_name: str, column_name: str) -> None:
    if _has_table(bind, table_name) and _has_column(bind, table_name, column_name):
        op.drop_column(table_name, column_name)
