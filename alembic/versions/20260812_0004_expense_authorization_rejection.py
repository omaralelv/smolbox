"""Support rejected authorization expenses.

Revision ID: 20260812_0004
Revises: 20260811_0003
Create Date: 2026-08-12 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_0004"
down_revision: str | None = "20260811_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if not _has_pg_enum(bind, "expense_status"):
        return

    op.execute("ALTER TYPE expense_status ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely without rebuilding the type.
    pass


def _has_pg_enum(bind, name: str) -> bool:
    result = bind.execute(
        sa.text("select 1 from pg_type where typname = :name"),
        {"name": name},
    )
    return result.scalar() is not None
