"""Enterprise approval workflow.

Revision ID: 20260811_0002
Revises: 20260811_0001
Create Date: 2026-08-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0002"
down_revision: str | None = "20260811_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    _ensure_enum_values(
        bind,
        "user_role",
        ["authorizer", "accounting_manager", "director"],
    )
    _ensure_enum_values(
        bind,
        "expense_status",
        ["removed"],
    )
    _ensure_enum_values(
        bind,
        "reimbursement_request_status",
        [
            "authorization_review",
            "authorized",
            "accounting_reviewed",
            "accounting_manager_review",
            "accounting_manager_approved",
            "direction_review",
            "direction_approved",
        ],
    )

    timestamp = sa.DateTime(timezone=True)
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("authorization_reviewed_at", timestamp),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("accounting_manager_reviewed_at", timestamp),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("direction_reviewed_at", timestamp),
    )
    _add_column_if_missing(
        bind,
        "reimbursement_requests",
        sa.Column("direction_approved_at", timestamp),
    )

    _add_column_if_missing(
        bind,
        "expenses",
        sa.Column(
            "requires_authorization",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    _add_column_if_missing(bind, "expenses", sa.Column("authorized_at", timestamp))
    _add_column_if_missing(
        bind,
        "expenses",
        sa.Column("authorized_by_user_id", sa.Uuid(), nullable=True),
    )
    _add_column_if_missing(bind, "expenses", sa.Column("authorization_note", sa.Text()))
    _add_column_if_missing(bind, "expenses", sa.Column("review_note", sa.Text()))
    _add_column_if_missing(bind, "expenses", sa.Column("removed_at", timestamp))
    _add_column_if_missing(
        bind,
        "expenses",
        sa.Column("removed_by_user_id", sa.Uuid(), nullable=True),
    )
    _add_column_if_missing(bind, "expenses", sa.Column("removal_reason", sa.Text()))

    _create_index_if_missing(
        bind,
        "ix_expenses_authorized_by_user_id",
        "expenses",
        ["authorized_by_user_id"],
    )
    _create_index_if_missing(
        bind,
        "ix_expenses_removed_by_user_id",
        "expenses",
        ["removed_by_user_id"],
    )
    if bind.dialect.name != "sqlite":
        _create_fk_if_missing(
            bind,
            "fk_expenses_authorized_by_user_id_users",
            "expenses",
            "users",
            ["authorized_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        _create_fk_if_missing(
            bind,
            "fk_expenses_removed_by_user_id_users",
            "expenses",
            "users",
            ["removed_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if bind.dialect.name != "sqlite" and _has_column(bind, "expenses", "requires_authorization"):
        op.alter_column("expenses", "requires_authorization", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        _drop_fk_if_exists(bind, "expenses", "fk_expenses_removed_by_user_id_users")
        _drop_fk_if_exists(bind, "expenses", "fk_expenses_authorized_by_user_id_users")
    _drop_index_if_exists(bind, "expenses", "ix_expenses_removed_by_user_id")
    _drop_index_if_exists(bind, "expenses", "ix_expenses_authorized_by_user_id")

    for column in [
        "removal_reason",
        "removed_by_user_id",
        "removed_at",
        "review_note",
        "authorization_note",
        "authorized_by_user_id",
        "authorized_at",
        "requires_authorization",
    ]:
        _drop_column_if_exists(bind, "expenses", column)

    for column in [
        "direction_approved_at",
        "direction_reviewed_at",
        "accounting_manager_reviewed_at",
        "authorization_reviewed_at",
    ]:
        _drop_column_if_exists(bind, "reimbursement_requests", column)


def _ensure_enum_values(bind, enum_name: str, values: list[str]) -> None:
    if bind.dialect.name != "postgresql" or not _has_pg_enum(bind, enum_name):
        return
    for value in values:
        op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")


def _has_pg_enum(bind, name: str) -> bool:
    result = bind.execute(sa.text("select 1 from pg_type where typname = :name"), {"name": name})
    return result.scalar() is not None


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


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    existing = {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(bind, table_name: str, index_name: str) -> None:
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
