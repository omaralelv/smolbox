"""Queues, payments, corrections and business rules.

Revision ID: 20260813_0005
Revises: 20260812_0004
Create Date: 2026-08-13 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260813_0005"
down_revision: str | None = "20260812_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        postgresql.ENUM("paid", "cancelled", name="payment_status").create(bind, checkfirst=True)

    timestamp = sa.DateTime(timezone=True)
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("correction_requested_at", timestamp, nullable=True),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("correction_requested_by_user_id", sa.Uuid(), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("correction_return_status", _reimbursement_status_type(bind), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("correction_reason", sa.Text(), nullable=True),
    )
    _create_index_if_missing(
        bind,
        "ix_reimbursement_requests_correction_requested_by_user_id",
        "reimbursement_requests",
        ["correction_requested_by_user_id"],
    )
    if bind.dialect.name != "sqlite":
        _create_fk_if_missing(
            bind,
            "fk_reimbursement_requests_correction_requested_by_user_id_users",
            "reimbursement_requests",
            "users",
            ["correction_requested_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _create_payments_if_missing(bind)
    _create_business_rules_if_missing(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _drop_table_if_exists(bind, "business_rules")
    _drop_table_if_exists(bind, "payments")
    if bind.dialect.name != "sqlite":
        _drop_fk_if_exists(
            bind,
            "reimbursement_requests",
            "fk_reimbursement_requests_correction_requested_by_user_id_users",
        )
    _drop_index_if_exists(
        bind,
        "reimbursement_requests",
        "ix_reimbursement_requests_correction_requested_by_user_id",
    )
    for column in [
        "correction_reason",
        "correction_return_status",
        "correction_requested_by_user_id",
        "correction_requested_at",
    ]:
        _drop_column_if_exists(bind, "reimbursement_requests", column)
    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="payment_status").drop(bind, checkfirst=True)


def _create_payments_if_missing(bind) -> None:
    if _has_table(bind, "payments"):
        return
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("reimbursement_request_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_method", sa.String(length=80), nullable=True),
        sa.Column("reference", sa.String(length=120), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", _payment_status_type(bind), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["reimbursement_request_id"],
            ["reimbursement_requests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["paid_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_payments_reimbursement_request_id", "payments", ["reimbursement_request_id"])
    op.create_index("ix_payments_paid_by_user_id", "payments", ["paid_by_user_id"])


def _create_business_rules_if_missing(bind) -> None:
    if _has_table(bind, "business_rules"):
        return
    op.create_table(
        "business_rules",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_business_rules_code"),
    )
    op.create_index("ix_business_rules_code", "business_rules", ["code"])


def _payment_status_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM("paid", "cancelled", name="payment_status", create_type=False)
    return sa.String(length=40)


def _reimbursement_status_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(name="reimbursement_request_status", create_type=False)
    return sa.String(length=80)


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    if not _has_table(bind, table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _add_column_if_missing(bind, table_name: str, column: sa.Column) -> None:
    if _has_table(bind, table_name) and not _has_column(bind, table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(bind, table_name: str, column_name: str) -> None:
    if _has_table(bind, table_name) and _has_column(bind, table_name, column_name):
        op.drop_column(table_name, column_name)


def _drop_table_if_exists(bind, table_name: str) -> None:
    if _has_table(bind, table_name):
        op.drop_table(table_name)


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _has_table(bind, table_name):
        return
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    if not _has_table(bind, table_name):
        return
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def _create_fk_if_missing(
    bind,
    fk_name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str,
) -> None:
    existing = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys(source_table)}
    if fk_name not in existing:
        op.create_foreign_key(
            fk_name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            ondelete=ondelete,
        )


def _drop_fk_if_exists(bind, table_name: str, fk_name: str) -> None:
    existing = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys(table_name)}
    if fk_name in existing:
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
