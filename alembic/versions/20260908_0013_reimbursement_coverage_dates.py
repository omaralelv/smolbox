"""Reimbursement coverage dates.

Revision ID: 20260908_0013
Revises: 20260908_0012
Create Date: 2026-09-08 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0013"
down_revision: str | None = "20260908_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reimbursement_requests",
        sa.Column(
            "reimbursement_starts_on",
            sa.Date(),
            nullable=True,
        ),
    )

    op.add_column(
        "reimbursement_requests",
        sa.Column(
            "reimbursement_ends_on",
            sa.Date(),
            nullable=True,
        ),
    )

    op.add_column(
        "reimbursement_requests",
        sa.Column(
            "previous_reimbursement_request_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_reimbursement_requests_previous_request",
        "reimbursement_requests",
        "reimbursement_requests",
        ["previous_reimbursement_request_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_check_constraint(
        "ck_reimbursement_request_coverage_dates",
        "reimbursement_requests",
        (
            "reimbursement_ends_on IS NULL "
            "OR reimbursement_starts_on IS NULL "
            "OR reimbursement_ends_on >= reimbursement_starts_on"
        ),
    )

    op.create_index(
        "ix_reimbursement_requests_store_coverage_end",
        "reimbursement_requests",
        [
            "store_id",
            "reimbursement_ends_on",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reimbursement_requests_store_coverage_end",
        table_name="reimbursement_requests",
    )

    op.drop_constraint(
        "ck_reimbursement_request_coverage_dates",
        "reimbursement_requests",
        type_="check",
    )

    op.drop_constraint(
        "fk_reimbursement_requests_previous_request",
        "reimbursement_requests",
        type_="foreignkey",
    )

    op.drop_column(
        "reimbursement_requests",
        "previous_reimbursement_request_id",
    )

    op.drop_column(
        "reimbursement_requests",
        "reimbursement_ends_on",
    )

    op.drop_column(
        "reimbursement_requests",
        "reimbursement_starts_on",
    )