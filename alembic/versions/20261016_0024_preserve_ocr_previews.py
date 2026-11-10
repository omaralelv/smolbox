"""Preserve full OCR readings before an expense or attachment exists."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_0024"
down_revision: str | None = "20261015_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("ocr_extractions")}
    with op.batch_alter_table("ocr_extractions") as batch:
        if not columns["attachment_id"]["nullable"]:
            batch.alter_column("attachment_id", existing_type=sa.Uuid(), nullable=True)
        if "document_checksum_sha256" not in columns:
            batch.add_column(sa.Column("document_checksum_sha256", sa.String(64), nullable=True))
        if "source_filename" not in columns:
            batch.add_column(sa.Column("source_filename", sa.String(255), nullable=True))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("ocr_extractions")}
    if "ix_ocr_extractions_document_checksum_sha256" not in indexes:
        op.create_index(
            "ix_ocr_extractions_document_checksum_sha256",
            "ocr_extractions", ["document_checksum_sha256"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT count(*) FROM ocr_extractions WHERE attachment_id IS NULL")).scalar_one():
        raise RuntimeError("Back up and resolve saved OCR previews before downgrading; no readings were deleted.")
    op.drop_index("ix_ocr_extractions_document_checksum_sha256", table_name="ocr_extractions")
    with op.batch_alter_table("ocr_extractions") as batch:
        batch.drop_column("source_filename")
        batch.drop_column("document_checksum_sha256")
        batch.alter_column("attachment_id", existing_type=sa.Uuid(), nullable=False)
