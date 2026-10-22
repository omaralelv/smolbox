"""Compatibility marker for a previously stamped opening cutoff revision.

Revision ID: bb529e163539
Revises: 20260908_0013
Create Date: 2026-09-09 00:00:00
"""

from collections.abc import Sequence

revision: str = "bb529e163539"
down_revision: str | None = "20260908_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op bridge for databases already stamped with this revision."""


def downgrade() -> None:
    """No-op bridge for databases already stamped with this revision."""
