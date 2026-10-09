"""Add category authorization rules.

Revision ID: 20260923_0020
Revises: 20260917_0019
Create Date: 2026-09-23 00:00:00
"""

import re
import unicodedata
import uuid
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260923_0020"
down_revision: str | None = "20260917_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY_AUTHORIZATION_RULES = (
    ("Agua", None, None, False),
    ("Alimentos", "Supervisores", None, True),
    ("Artículos de Limpieza", "Supervisores", Decimal("600.00"), True),
    ("Bolsas", "Insumos", Decimal("50.00"), True),
    ("Energía Eléctrica", "Contabilidad", None, True),
    ("Equipo de Cómputo Menor", "Sistemas", None, True),
    ("Mantenimiento Equipo de Computo", "Sistemas", None, True),
    ("Equipo Menor", "Supervisores", None, True),
    ("Extintores y Protección Civil", "Gestoría", None, True),
    ("Gasolina", "Supervisores", None, True),
    ("Hospedaje", "Supervisores", None, True),
    ("Licencias y Permisos", "Gestoría", None, True),
    ("Medicamentos", "Gestoría", None, True),
    ("No Deducibles", "Supervisores", None, True),
    ("Papelería", "Insumos", Decimal("600.00"), True),
    ("Paquetería y Mensajería", "Supervisores", None, True),
    ("Publicidad", "Supervisores", None, True),
    ("Recolección de Basura", "Gestoría", None, True),
    ("Servicio de Agua", "Servicio de Agua", None, True),
    ("Teléfono", "Sistemas", None, True),
    ("Transportación", "Supervisores", None, True),
    ("Trasportación", "Supervisores", None, True),
    ("Transporte", "Supervisores", None, True),
    ("Otros (merceria)", "Supervisores", Decimal("100.00"), True),
    ("Otros", "Supervisores", Decimal("100.00"), True),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "category_authorization_rules"):
        op.create_table(
            "category_authorization_rules",
            sa.Column("id", _uuid_type(bind), primary_key=True, nullable=False),
            sa.Column("category", sa.String(length=120), nullable=False),
            sa.Column("normalized_category", sa.String(length=120), nullable=False),
            sa.Column("authorization_area_id", _uuid_type(bind), nullable=True),
            sa.Column("minimum_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column(
                "requires_authorization",
                sa.Boolean(),
                nullable=False,
                server_default=_bool_default(bind, True),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=_bool_default(bind, True),
            ),
            sa.Column("source", sa.String(length=80), nullable=True),
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
                ["authorization_area_id"],
                ["authorization_areas.id"],
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint(
                "normalized_category",
                name="uq_category_authorization_rules_normalized_category",
            ),
        )

    _create_index_if_missing(
        bind,
        "ix_category_authorization_rules_normalized_category",
        "category_authorization_rules",
        ["normalized_category"],
    )
    _create_index_if_missing(
        bind,
        "ix_category_authorization_rules_authorization_area_id",
        "category_authorization_rules",
        ["authorization_area_id"],
    )
    _seed_rules(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "category_authorization_rules"):
        op.drop_table("category_authorization_rules")


def _seed_rules(bind) -> None:
    if not _has_table(bind, "authorization_areas"):
        return
    if not _has_table(bind, "category_authorization_rules"):
        return

    existing_rules = set(
        bind.execute(
            sa.text("SELECT normalized_category FROM category_authorization_rules")
        ).scalars()
    )
    for category, area_name, minimum_amount, requires_authorization in (
        CATEGORY_AUTHORIZATION_RULES
    ):
        normalized_category = _normalize(category)
        if normalized_category in existing_rules:
            continue

        authorization_area_id = None
        if area_name:
            authorization_area_id = _get_or_create_area_id(bind, area_name)

        bind.execute(
            sa.text(
                """
                INSERT INTO category_authorization_rules
                    (
                        id,
                        category,
                        normalized_category,
                        authorization_area_id,
                        minimum_amount,
                        requires_authorization,
                        is_active,
                        source
                    )
                VALUES
                    (
                        :id,
                        :category,
                        :normalized_category,
                        :authorization_area_id,
                        :minimum_amount,
                        :requires_authorization,
                        :is_active,
                        :source
                    )
                """
            ),
            {
                "id": _stable_uuid(bind, f"category_rule.{normalized_category}"),
                "category": category,
                "normalized_category": normalized_category,
                "authorization_area_id": authorization_area_id,
                "minimum_amount": minimum_amount,
                "requires_authorization": requires_authorization,
                "is_active": True,
                "source": "built_in",
            },
        )
        existing_rules.add(normalized_category)


def _get_or_create_area_id(bind, area_name: str):
    normalized_name = _normalize(area_name)
    result = bind.execute(
        sa.text(
            """
            SELECT id
            FROM authorization_areas
            WHERE normalized_name = :normalized_name
            """
        ),
        {"normalized_name": normalized_name},
    ).scalar()
    if result is not None:
        return result

    area_id = _stable_uuid(bind, f"authorization_area.{normalized_name}")
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
            "id": area_id,
            "name": area_name,
            "normalized_name": normalized_name,
            "is_active": True,
        },
    )
    return area_id


def _stable_uuid(bind, value: str) -> str:
    stable_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"smolbox.{value}")
    if bind.dialect.name == "sqlite":
        return stable_uuid.hex
    return str(stable_uuid)


def _normalize(value: str) -> str:
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


def _has_index(bind, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _create_index_if_missing(
    bind,
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _has_index(bind, table_name, index_name):
        op.create_index(index_name, table_name, columns)
