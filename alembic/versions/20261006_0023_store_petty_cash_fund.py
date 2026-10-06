"""Add petty cash fund to stores.

Revision ID: 20261006_0023
Revises: 20261004_0022
Create Date: 2026-10-06 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261006_0023"
down_revision: str | None = "20261004_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "stores" not in inspector.get_table_names():
        return
    if any(column["name"] == "petty_cash_fund" for column in inspector.get_columns("stores")):
        return

    op.add_column(
        "stores",
        sa.Column(
            "petty_cash_fund",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "stores" not in inspector.get_table_names():
        return
    if any(column["name"] == "petty_cash_fund" for column in inspector.get_columns("stores")):
        op.drop_column("stores", "petty_cash_fund")
