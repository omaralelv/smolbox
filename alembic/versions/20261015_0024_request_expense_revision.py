"""Track policy and reimbursement artifacts against request expense revisions.

Revision ID: 20261015_0024
Revises: 20261006_0023
Create Date: 2026-10-15 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261015_0024"
down_revision: str | None = "20261006_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reimbursement_requests" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("reimbursement_requests")}
    if "expense_content_revision" not in columns:
        op.add_column(
            "reimbursement_requests",
            sa.Column(
                "expense_content_revision",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    if "policy_downloaded_revision" not in columns:
        op.add_column(
            "reimbursement_requests",
            sa.Column("policy_downloaded_revision", sa.Integer(), nullable=True),
        )
    if "reimbursement_excel_revision" not in columns:
        op.add_column(
            "reimbursement_requests",
            sa.Column("reimbursement_excel_revision", sa.Integer(), nullable=True),
        )
    if "artifacts_refresh_required" not in columns:
        op.add_column(
            "reimbursement_requests",
            sa.Column(
                "artifacts_refresh_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "reimbursement_requests" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("reimbursement_requests")}
    for column_name in (
        "reimbursement_excel_revision",
        "policy_downloaded_revision",
        "artifacts_refresh_required",
        "expense_content_revision",
    ):
        if column_name in columns:
            op.drop_column("reimbursement_requests", column_name)
