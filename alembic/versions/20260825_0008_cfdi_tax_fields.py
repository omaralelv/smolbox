"""Add CFDI tax fields.

Revision ID: 20260825_0008
Revises: 20260821_0007
Create Date: 2026-08-25 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_0008"
down_revision: str | None = "20260821_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    money = sa.Numeric(12, 2)
    rate = sa.Numeric(5, 2)

    if _has_table(bind, "expenses"):
        _add_column_if_missing(bind, "expenses", sa.Column("cfdi_subtotal", money))
        _add_column_if_missing(bind, "expenses", sa.Column("cfdi_tax_amount", money))
        _add_column_if_missing(bind, "expenses", sa.Column("cfdi_tax_rate", rate))

    if _has_table(bind, "cfdi_validations"):
        _add_column_if_missing(bind, "cfdi_validations", sa.Column("subtotal", money))
        _add_column_if_missing(bind, "cfdi_validations", sa.Column("tax_amount", money))
        _add_column_if_missing(bind, "cfdi_validations", sa.Column("tax_rate", rate))


def downgrade() -> None:
    bind = op.get_bind()
    for column_name in ["cfdi_tax_rate", "cfdi_tax_amount", "cfdi_subtotal"]:
        _drop_column_if_exists(bind, "expenses", column_name)
    for column_name in ["tax_rate", "tax_amount", "subtotal"]:
        _drop_column_if_exists(bind, "cfdi_validations", column_name)


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _add_column_if_missing(bind, table_name: str, column: sa.Column) -> None:
    if not _has_column(bind, table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(bind, table_name: str, column_name: str) -> None:
    if _has_table(bind, table_name) and _has_column(bind, table_name, column_name):
        op.drop_column(table_name, column_name)
