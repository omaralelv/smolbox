"""Keep receiver OCR comparison separate from the original reading."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261016_0025"
down_revision: str | None = "20261016_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("ocr_extractions")}
    if "receiver_validation" not in columns:
        op.add_column("ocr_extractions", sa.Column("receiver_validation", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ocr_extractions") as batch:
        batch.drop_column("receiver_validation")
