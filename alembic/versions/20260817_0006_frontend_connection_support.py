"""Frontend connection support.

Revision ID: 20260817_0006
Revises: 20260813_0005
Create Date: 2026-08-17 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260817_0006"
down_revision: str | None = "20260813_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    _add_column_if_missing(bind, "stores", sa.Column("manager_name", sa.String(length=160)))
    _add_column_if_missing(bind, "stores", sa.Column("bank_account", sa.String(length=80)))
    _add_column_if_missing(bind, "stores", sa.Column("state_region", sa.String(length=120)))

    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("folio", sa.String(length=80), nullable=True),
    )
    _drop_unique_constraint_if_exists(
        bind,
        "reimbursement_requests",
        "uq_reimbursement_requests_store_period",
    )
    _create_index_if_missing(
        bind,
        "ix_reimbursement_requests_folio",
        "reimbursement_requests",
        ["folio"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    _drop_index_if_exists(bind, "reimbursement_requests", "ix_reimbursement_requests_folio")
    _drop_column_if_exists(bind, "reimbursement_requests", "folio")
    if _has_table(bind, "reimbursement_requests"):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("reimbursement_requests") as batch_op:
                batch_op.create_unique_constraint(
                    "uq_reimbursement_requests_store_period",
                    ["store_id", "period_id"],
                )
        else:
            op.create_unique_constraint(
                "uq_reimbursement_requests_store_period",
                "reimbursement_requests",
                ["store_id", "period_id"],
            )
    for column in ["state_region", "bank_account", "manager_name"]:
        _drop_column_if_exists(bind, "stores", column)


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


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if not _has_table(bind, table_name):
        return
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    if not _has_table(bind, table_name):
        return
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def _drop_unique_constraint_if_exists(bind, table_name: str, constraint_name: str) -> None:
    if not _has_table(bind, table_name):
        return
    existing = {
        constraint["name"] for constraint in sa.inspect(bind).get_unique_constraints(table_name)
    }
    if constraint_name not in existing:
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")
    else:
        op.drop_constraint(constraint_name, table_name, type_="unique")
