"""Persist a manual SAP tax index override.

Revision ID: 20261002_0021
Revises: 20260923_0020
Create Date: 2026-10-02 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261002_0021"
down_revision: str | None = "20260923_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "expenses",
        sa.Column("sap_tax_index_override", sa.String(length=3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("expenses", "sap_tax_index_override")
