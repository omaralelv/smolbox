"""Create OCR extraction records.

Revision ID: 20260908_0012
Revises: 20260902_0011
Create Date: 2026-09-08 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260908_0012"
down_revision: str | None = "20260902_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "ocr_extractions"):
        return

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            "succeeded",
            "failed",
            name="ocr_extraction_status",
        ).create(bind, checkfirst=True)

    op.create_table(
        "ocr_extractions",
        sa.Column("id", _uuid_type(bind), primary_key=True, nullable=False),
        sa.Column(
            "attachment_id",
            _uuid_type(bind),
            sa.ForeignKey("attachments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expense_id",
            _uuid_type(bind),
            sa.ForeignKey("expenses.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("status", _status_type(bind), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("extracted_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("extracted_date", sa.Date(), nullable=True),
        sa.Column("extracted_supplier", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("attachment_id", name="uq_ocr_extractions_attachment_id"),
    )
    op.create_index(
        "ix_ocr_extractions_attachment_id",
        "ocr_extractions",
        ["attachment_id"],
    )
    op.create_index("ix_ocr_extractions_expense_id", "ocr_extractions", ["expense_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "ocr_extractions"):
        op.drop_index("ix_ocr_extractions_expense_id", table_name="ocr_extractions")
        op.drop_index("ix_ocr_extractions_attachment_id", table_name="ocr_extractions")
        op.drop_table("ocr_extractions")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(name="ocr_extraction_status").drop(bind, checkfirst=True)


def _uuid_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.Uuid()


def _status_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.ENUM(
            "succeeded",
            "failed",
            name="ocr_extraction_status",
            create_type=False,
        )
    return sa.Enum("succeeded", "failed", name="ocr_extraction_status")


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()
