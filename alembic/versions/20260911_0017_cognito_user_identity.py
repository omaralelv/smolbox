"""Add Cognito identity to users.

Revision ID: 20260911_0017
Revises: 20260910_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_0017"
down_revision: str | None = "20260910_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "users", "cognito_sub"):
        op.add_column("users", sa.Column("cognito_sub", sa.String(length=255), nullable=True))
    if not _has_index(bind, "users", "ix_users_cognito_sub"):
        op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_index(bind, "users", "ix_users_cognito_sub"):
        op.drop_index("ix_users_cognito_sub", table_name="users")
    if _has_column(bind, "users", "cognito_sub"):
        op.drop_column("users", "cognito_sub")


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _has_index(bind, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
