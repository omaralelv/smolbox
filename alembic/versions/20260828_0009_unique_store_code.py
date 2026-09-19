"""add unique constraint to store code

Revision ID: 20260828_0009
Revises: 20260825_0008
Create Date: 2026-08-28
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260828_0009"
down_revision = "20260825_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_stores_code",
        "stores",
        ["code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_stores_code",
        "stores",
        type_="unique",
    )
