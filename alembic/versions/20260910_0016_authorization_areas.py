"""Add authorization areas.

Revision ID: 20260910_0016
Revises: 20260909_0015
Create Date: 2026-09-10 00:00:00
"""

from collections.abc import Sequence
import re
import unicodedata
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260910_0016"
down_revision: str | None = "20260909_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_AUTHORIZATION_AREA_NAMES = (
    "Auditoría Interna",
    "Gestoría",
    "Insumos",
    "Mantenimiento",
    "Operaciones",
    "Pago de Luz",
    "Recursos Humanos",
    "Servicio de Agua",
    "Sistemas",
    "Supervisores",
    "Tráfico",
)


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "authorization_areas"):
        op.create_table(
            "authorization_areas",
            sa.Column("id", _uuid_type(bind), primary_key=True, nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("normalized_name", sa.String(length=120), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=_bool_default(bind, True),
            ),
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
            sa.UniqueConstraint(
                "normalized_name",
                name="uq_authorization_areas_normalized_name",
            ),
        )

    _seed_default_authorization_areas(bind)

    if not _has_table(bind, "user_authorization_areas"):
        op.create_table(
            "user_authorization_areas",
            sa.Column("id", _uuid_type(bind), primary_key=True, nullable=False),
            sa.Column("user_id", _uuid_type(bind), nullable=False),
            sa.Column("authorization_area_id", _uuid_type(bind), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=_bool_default(bind, True),
            ),
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
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["authorization_area_id"],
                ["authorization_areas.id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "user_id",
                "authorization_area_id",
                name="uq_user_authorization_areas_user_area",
            ),
        )

    _create_index_if_missing(
        bind,
        "ix_user_authorization_areas_user_id",
        "user_authorization_areas",
        ["user_id"],
    )
    _create_index_if_missing(
        bind,
        "ix_user_authorization_areas_authorization_area_id",
        "user_authorization_areas",
        ["authorization_area_id"],
    )

    if _has_table(bind, "expenses"):
        _add_column_if_missing(
            "expenses",
            sa.Column("authorization_area_id", _uuid_type(bind), nullable=True),
        )
        _create_index_if_missing(
            bind,
            "ix_expenses_authorization_area_id",
            "expenses",
            ["authorization_area_id"],
        )

        if bind.dialect.name != "sqlite" and not _has_foreign_key(
            bind,
            "expenses",
            "fk_expenses_authorization_area",
        ):
            op.create_foreign_key(
                "fk_expenses_authorization_area",
                "expenses",
                "authorization_areas",
                ["authorization_area_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_table(bind, "expenses"):
        if bind.dialect.name != "sqlite" and _has_foreign_key(
            bind,
            "expenses",
            "fk_expenses_authorization_area",
        ):
            op.drop_constraint(
                "fk_expenses_authorization_area",
                "expenses",
                type_="foreignkey",
            )
        if _has_index(bind, "expenses", "ix_expenses_authorization_area_id"):
            op.drop_index("ix_expenses_authorization_area_id", table_name="expenses")
        if _has_column(bind, "expenses", "authorization_area_id"):
            op.drop_column("expenses", "authorization_area_id")

    if _has_table(bind, "user_authorization_areas"):
        op.drop_table("user_authorization_areas")

    if _has_table(bind, "authorization_areas"):
        op.drop_table("authorization_areas")


def _seed_default_authorization_areas(bind) -> None:
    if not _has_table(bind, "authorization_areas"):
        return

    existing = set(
        bind.execute(sa.text("SELECT normalized_name FROM authorization_areas")).scalars()
    )
    for name in DEFAULT_AUTHORIZATION_AREA_NAMES:
        normalized_name = _normalize_area_name(name)
        if normalized_name in existing:
            continue

        bind.execute(
            sa.text(
                """
                INSERT INTO authorization_areas
                    (id, name, normalized_name, is_active)
                VALUES
                    (:id, :name, :normalized_name, :is_active)
                """
            ),
            {
                "id": _stable_uuid(bind, normalized_name),
                "name": name,
                "normalized_name": normalized_name,
                "is_active": True,
            },
        )
        existing.add(normalized_name)


def _stable_uuid(bind, normalized_name: str) -> str:
    area_uuid = uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"smolbox.authorization_area.{normalized_name}",
    )
    if bind.dialect.name == "sqlite":
        return area_uuid.hex
    return str(area_uuid)


def _normalize_area_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", without_accents.upper())
    return re.sub(r"\s+", " ", normalized).strip()


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


def _bool_default(bind, value: bool):
    if bind.dialect.name == "postgresql":
        return sa.text("true" if value else "false")
    return sa.text("1" if value else "0")


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


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _has_index(bind, table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    bind = op.get_bind()
    if not _has_column(bind, table_name, column.name):
        op.add_column(table_name, column)
