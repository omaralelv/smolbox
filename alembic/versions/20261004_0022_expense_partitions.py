"""Track expense partitions.

Revision ID: 20261004_0022
Revises: 20261002_0021
Create Date: 2026-10-04 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261004_0022"
down_revision: str | None = "20261002_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "expenses"):
        return

    if not _has_column(bind, "expenses", "partition_parent_expense_id"):
        op.add_column(
            "expenses",
            sa.Column("partition_parent_expense_id", sa.Uuid(), nullable=True),
        )
    if not _has_column(bind, "expenses", "partition_index"):
        op.add_column("expenses", sa.Column("partition_index", sa.Integer(), nullable=True))
    if not _has_column(bind, "expenses", "partition_count"):
        op.add_column("expenses", sa.Column("partition_count", sa.Integer(), nullable=True))

    if not _has_index(bind, "expenses", "ix_expenses_partition_parent_expense_id"):
        op.create_index(
            "ix_expenses_partition_parent_expense_id",
            "expenses",
            ["partition_parent_expense_id"],
        )

    if not _has_foreign_key(bind, "expenses", "fk_expenses_partition_parent_expense_id"):
        op.create_foreign_key(
            "fk_expenses_partition_parent_expense_id",
            "expenses",
            "expenses",
            ["partition_parent_expense_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "expenses"):
        return

    if _has_foreign_key(bind, "expenses", "fk_expenses_partition_parent_expense_id"):
        op.drop_constraint(
            "fk_expenses_partition_parent_expense_id",
            "expenses",
            type_="foreignkey",
        )
    if _has_index(bind, "expenses", "ix_expenses_partition_parent_expense_id"):
        op.drop_index("ix_expenses_partition_parent_expense_id", table_name="expenses")
    if _has_column(bind, "expenses", "partition_count"):
        op.drop_column("expenses", "partition_count")
    if _has_column(bind, "expenses", "partition_index"):
        op.drop_column("expenses", "partition_index")
    if _has_column(bind, "expenses", "partition_parent_expense_id"):
        op.drop_column("expenses", "partition_parent_expense_id")


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_foreign_key(bind, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        fk.get("name") == constraint_name
        for fk in inspector.get_foreign_keys(table_name)
    )
