"""Add suggested CFDI UUID to OCR extractions.

Revision ID: 20260915_0018
Revises: 20260911_0017
Create Date: 2026-09-15 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260915_0018"
down_revision: str | None = "20260911_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "ocr_extractions") and not _has_column(
        bind,
        "ocr_extractions",
        "suggested_cfdi_uuid",
    ):
        op.add_column(
            "ocr_extractions",
            sa.Column("suggested_cfdi_uuid", sa.String(length=36), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "ocr_extractions") and _has_column(
        bind,
        "ocr_extractions",
        "suggested_cfdi_uuid",
    ):
        op.drop_column("ocr_extractions", "suggested_cfdi_uuid")


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _has_column(bind, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
