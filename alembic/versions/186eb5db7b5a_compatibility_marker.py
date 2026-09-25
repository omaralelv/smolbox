"""Compatibility marker for a previously stamped local revision.

Revision ID: 186eb5db7b5a
Revises: 20260908_0012
Create Date: 2026-09-08 00:00:00
"""

from collections.abc import Sequence

revision: str = "186eb5db7b5a"
down_revision: str | None = "20260908_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op bridge for databases already stamped with this revision."""


def downgrade() -> None:
    """No-op bridge for databases already stamped with this revision."""
