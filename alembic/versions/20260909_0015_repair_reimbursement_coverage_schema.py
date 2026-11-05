"""Repair reimbursement coverage schema.

Revision ID: 20260909_0015
Revises: 20260908_0014
Create Date: 2026-09-09 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260909_0015"
down_revision: str | None = "20260908_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_opening_cutoffs_table(bind)

    if not _has_table(bind, "reimbursement_requests"):
        return

    _add_column_if_missing(
        "reimbursement_requests",
        sa.Column("reimbursement_starts_on", sa.Date(), nullable=True),
    )
    _add_column_if_missing(
        "reimbursement_requests",
        sa.Column("reimbursement_ends_on", sa.Date(), nullable=True),
    )
    _add_column_if_missing(
        "reimbursement_requests",
        sa.Column("previous_reimbursement_request_id", _uuid_type(bind), nullable=True),
    )

    if not _has_index(
        bind,
        "reimbursement_requests",
        "ix_reimbursement_requests_previous_request_id",
    ):
        op.create_index(
            "ix_reimbursement_requests_previous_request_id",
            "reimbursement_requests",
            ["previous_reimbursement_request_id"],
        )

    if not _has_index(
        bind,
        "reimbursement_requests",
        "ix_reimbursement_requests_store_coverage_end",
    ):
        op.create_index(
            "ix_reimbursement_requests_store_coverage_end",
            "reimbursement_requests",
            ["store_id", "reimbursement_ends_on"],
        )

    if bind.dialect.name == "sqlite":
        return

    if not _has_foreign_key(
        bind,
        "reimbursement_requests",
        "fk_reimbursement_requests_previous_request",
    ):
        op.create_foreign_key(
            "fk_reimbursement_requests_previous_request",
            "reimbursement_requests",
            "reimbursement_requests",
            ["previous_reimbursement_request_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not _has_check_constraint(
        bind,
        "reimbursement_requests",
        "ck_reimbursement_request_coverage_dates",
    ):
        op.create_check_constraint(
            "ck_reimbursement_request_coverage_dates",
            "reimbursement_requests",
            (
                "reimbursement_ends_on IS NULL "
                "OR reimbursement_starts_on IS NULL "
                "OR reimbursement_ends_on >= reimbursement_starts_on"
            ),
        )


def downgrade() -> None:
    # No-op on purpose: this repair may add objects expected by older migrations.
    # Dropping them here could re-break a database that was repaired by upgrade().
    return


def _uuid_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid()


def _timestamp_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.TIMESTAMP(timezone=True)
    return sa.DateTime(timezone=True)


def _now_default(bind):
    if bind.dialect.name == "postgresql":
        return sa.text("now()")
    return sa.text("CURRENT_TIMESTAMP")


def _ensure_opening_cutoffs_table(bind) -> None:
    if _has_table(bind, "store_reimbursement_opening_cutoffs") or not _has_table(bind, "stores"):
        return

    op.create_table(
        "store_reimbursement_opening_cutoffs",
        sa.Column("id", _uuid_type(bind), primary_key=True, nullable=False),
        sa.Column("store_id", _uuid_type(bind), nullable=False),
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
            _timestamp_type(bind),
            nullable=False,
            server_default=_now_default(bind),
        ),
        sa.Column(
            "updated_at",
            _timestamp_type(bind),
            nullable=False,
            server_default=_now_default(bind),
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("store_id", name="uq_store_reimbursement_opening_cutoff"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_opening_cutoff_dates"),
    )


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _has_index(bind, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _has_foreign_key(bind, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {
        constraint["name"] for constraint in sa.inspect(bind).get_foreign_keys(table_name)
    }


def _has_check_constraint(bind, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {
        constraint["name"] for constraint in sa.inspect(bind).get_check_constraints(table_name)
    }


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if not _has_column(bind, table_name, column.name):
        op.add_column(table_name, column)
