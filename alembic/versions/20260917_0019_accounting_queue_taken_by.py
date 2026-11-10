"""Track the user who takes an accounting queue request.

Revision ID: 20260917_0019
Revises: 20260915_0018
Create Date: 2026-09-17 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260917_0019"
down_revision: str | None = "20260915_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "reimbursement_requests") and not _has_column(
        bind,
        "reimbursement_requests",
        "accounting_queue_taken_by_user_id",
    ):
        op.add_column(
            "reimbursement_requests",
            sa.Column(
                "accounting_queue_taken_by_user_id",
                sa.Uuid(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_reimbursement_requests_accounting_queue_taken_by_user_id",
            "reimbursement_requests",
            ["accounting_queue_taken_by_user_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "reimbursement_requests") and _has_column(
        bind,
        "reimbursement_requests",
        "accounting_queue_taken_by_user_id",
    ):
        op.drop_index(
            "ix_reimbursement_requests_accounting_queue_taken_by_user_id",
            table_name="reimbursement_requests",
        )
        op.drop_column("reimbursement_requests", "accounting_queue_taken_by_user_id")


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
