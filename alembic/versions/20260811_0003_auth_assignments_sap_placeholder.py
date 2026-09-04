"""Auth assignments and SAP policy placeholder.

Revision ID: 20260811_0003
Revises: 20260811_0002
Create Date: 2026-08-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0003"
down_revision: str | None = "20260811_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    _add_column_if_missing(
        bind,
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )

    _create_store_user_assignments_if_missing(bind)

    timestamp = sa.DateTime(timezone=True)
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("sap_policy_generated_at", timestamp, nullable=True),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("sap_policy_generated_by_user_id", sa.Uuid(), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("sap_policy_reference", sa.String(length=120), nullable=True),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("sap_policy_payload", sa.JSON(), nullable=True),
    )
    _create_index_if_missing(
        bind,
        "ix_reimbursement_requests_sap_policy_generated_by_user_id",
        "reimbursement_requests",
        ["sap_policy_generated_by_user_id"],
    )
    if bind.dialect.name != "sqlite":
        _create_fk_if_missing(
            bind,
            "fk_reimbursement_requests_sap_policy_generated_by_user_id_users",
            "reimbursement_requests",
            "users",
            ["sap_policy_generated_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        _drop_fk_if_exists(
            bind,
            "reimbursement_requests",
            "fk_reimbursement_requests_sap_policy_generated_by_user_id_users",
        )
    _drop_index_if_exists(
        bind,
        "reimbursement_requests",
        "ix_reimbursement_requests_sap_policy_generated_by_user_id",
    )
    for column in [
        "sap_policy_payload",
        "sap_policy_reference",
        "sap_policy_generated_by_user_id",
        "sap_policy_generated_at",
    ]:
        _drop_column_if_exists(bind, "reimbursement_requests", column)

    _drop_table_if_exists(bind, "store_user_assignments")
    _drop_column_if_exists(bind, "users", "password_hash")


def _create_store_user_assignments_if_missing(bind) -> None:
    if _has_table(bind, "store_user_assignments"):
        return
    op.create_table(
        "store_user_assignments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("store_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("store_id", "user_id", name="uq_store_user_assignments_store_user"),
    )
    op.create_index("ix_store_user_assignments_store_id", "store_user_assignments", ["store_id"])
    op.create_index("ix_store_user_assignments_user_id", "store_user_assignments", ["user_id"])


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    if not _has_table(bind, table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _add_column_if_missing(bind, table_name: str, column: sa.Column) -> None:
    if _has_table(bind, table_name) and not _has_column(bind, table_name, column.name):
        op.add_column(table_name, column)


def _drop_column_if_exists(bind, table_name: str, column_name: str) -> None:
    if _has_table(bind, table_name) and _has_column(bind, table_name, column_name):
        op.drop_column(table_name, column_name)


def _drop_table_if_exists(bind, table_name: str) -> None:
    if _has_table(bind, table_name):
        op.drop_table(table_name)


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _has_table(bind, table_name):
        return
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
    if not _has_table(bind, table_name):
        return
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name in existing:
        op.drop_index(index_name, table_name=table_name)


def _create_fk_if_missing(
    bind,
    fk_name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str,
) -> None:
    existing = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys(source_table)}
    if fk_name not in existing:
        op.create_foreign_key(
            fk_name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            ondelete=ondelete,
        )


def _drop_fk_if_exists(bind, table_name: str, fk_name: str) -> None:
    existing = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys(table_name)}
    if fk_name in existing:
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
