"""Create new table store_spending_baselines.

Revision ID: 20260902_0011
Revises: 20260901_0010
Create Date: 2026-09-02 00:00:00
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260902_0011"
down_revision: str | None = "20260901_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "store_spending_baselines"):
        return

    op.create_table(
        "store_spending_baselines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stores.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fiscal_year",
            sa.SmallInteger(),
            nullable=False,
        ),
        sa.Column(
            "historical_amount",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "baseline_as_of",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            server_default="excel_import",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "store_id",
            "fiscal_year",
            name="uq_store_spending_baseline_store_year",
        ),
        sa.CheckConstraint(
            "fiscal_year >= 2000",
            name="ck_store_spending_baseline_valid_year",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "store_spending_baselines"):
        op.drop_table("store_spending_baselines")


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()
