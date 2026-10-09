"""Relax store code uniqueness.

Revision ID: 20260821_0007
Revises: 20260817_0006
Create Date: 2026-08-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_0007"
down_revision: str | None = "20260817_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "stores"):
        return

    _drop_unique_constraints_for_column(bind, "stores", "code")
    _drop_unique_indexes_for_column(bind, "stores", "code")
    _create_index_if_missing(bind, "ix_stores_code", "stores", ["code"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "stores"):
        return

    _drop_index_if_exists(bind, "stores", "ix_stores_code")
    op.create_index("ix_stores_code", "stores", ["code"], unique=True)


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _drop_unique_constraints_for_column(bind, table_name: str, column_name: str) -> None:
    constraints = sa.inspect(bind).get_unique_constraints(table_name)
    for constraint in constraints:
        if constraint.get("column_names") == [column_name] and constraint.get("name"):
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table(table_name) as batch_op:
                    batch_op.drop_constraint(constraint["name"], type_="unique")
            else:
                op.drop_constraint(constraint["name"], table_name, type_="unique")


def _drop_unique_indexes_for_column(bind, table_name: str, column_name: str) -> None:
    indexes = sa.inspect(bind).get_indexes(table_name)
    for index in indexes:
        if index.get("column_names") == [column_name] and index.get("unique"):
            op.drop_index(index["name"], table_name=table_name)


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)
