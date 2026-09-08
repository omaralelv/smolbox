"""Reimbursement coverage dates.

Revision ID: 20260908_0013
Revises: 186eb5db7b5a
Create Date: 2026-09-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260908_0013"
down_revision: str | None = "186eb5db7b5a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "reimbursement_requests"):
        return

    _add_column_if_missing(
        "reimbursement_requests",
        sa.Column(
            "reimbursement_starts_on",
            sa.Date(),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "reimbursement_requests",
        sa.Column(
            "reimbursement_ends_on",
            sa.Date(),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "reimbursement_requests",
        sa.Column(
            "previous_reimbursement_request_id",
            _uuid_type(bind),
            nullable=True,
        ),
    )

    if bind.dialect.name != "sqlite" and not _has_foreign_key(
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

    if bind.dialect.name != "sqlite" and not _has_check_constraint(
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

    if not _has_index(bind, "reimbursement_requests", "ix_reimbursement_requests_store_coverage_end"):
        op.create_index(
            "ix_reimbursement_requests_store_coverage_end",
            "reimbursement_requests",
            [
                "store_id",
                "reimbursement_ends_on",
            ],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "reimbursement_requests"):
        return

    if _has_index(bind, "reimbursement_requests", "ix_reimbursement_requests_store_coverage_end"):
        op.drop_index(
            "ix_reimbursement_requests_store_coverage_end",
            table_name="reimbursement_requests",
        )

    if bind.dialect.name != "sqlite" and _has_check_constraint(
        bind,
        "reimbursement_requests",
        "ck_reimbursement_request_coverage_dates",
    ):
        op.drop_constraint(
            "ck_reimbursement_request_coverage_dates",
            "reimbursement_requests",
            type_="check",
        )

    if bind.dialect.name != "sqlite" and _has_foreign_key(
        bind,
        "reimbursement_requests",
        "fk_reimbursement_requests_previous_request",
    ):
        op.drop_constraint(
            "fk_reimbursement_requests_previous_request",
            "reimbursement_requests",
            type_="foreignkey",
        )

    _drop_column_if_exists("reimbursement_requests", "previous_reimbursement_request_id")
    _drop_column_if_exists("reimbursement_requests", "reimbursement_ends_on")
    _drop_column_if_exists("reimbursement_requests", "reimbursement_starts_on")


def _uuid_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid()


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


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    if _has_column(bind, table_name, column_name):
        op.drop_column(table_name, column_name)
