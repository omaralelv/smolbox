"""Add store reimbursement opening cutoffs

Revision ID: 20260908_0014
Revises: 20260908_0013
Create Date: 2026-09-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260908_0014"
down_revision: str | None = "20260908_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "store_reimbursement_opening_cutoffs"):
        return

    op.create_table(
        "store_reimbursement_opening_cutoffs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column(
            "reimbursed_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("store_id", name="uq_store_reimbursement_opening_cutoff"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_opening_cutoff_dates"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "store_reimbursement_opening_cutoffs"):
        op.drop_table("store_reimbursement_opening_cutoffs")


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()
