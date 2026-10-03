"""Add accounting queue status.

Revision ID: 20260901_0010
Revises: 20260828_0009
Create Date: 2026-09-01 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op

revision: str = "20260901_0010"
down_revision: str | None = "20260828_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    accounting_status = sa.Enum("single", "taken", name="accounting_queue_status")
    if bind.dialect.name == "postgresql":
        accounting_status.create(bind, checkfirst=True)

    if context.is_offline_mode():
        op.add_column(
            "reimbursement_requests",
            sa.Column("accounting_queue_status", accounting_status, nullable=True),
        )
        return

    if _has_table(bind, "reimbursement_requests") and not _has_column(
        bind,
        "reimbursement_requests",
        "accounting_queue_status",
    ):
        op.add_column(
            "reimbursement_requests",
            sa.Column("accounting_queue_status", accounting_status, nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "reimbursement_requests") and _has_column(
        bind,
        "reimbursement_requests",
        "accounting_queue_status",
    ):
        op.drop_column("reimbursement_requests", "accounting_queue_status")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="accounting_queue_status").drop(bind, checkfirst=True)


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
