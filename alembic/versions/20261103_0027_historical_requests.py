"""Independent informational extemporaneous archive."""

import sqlalchemy as sa

from alembic import op

revision = "20261103_0027"
down_revision = "20261028_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("store_id", sa.Uuid(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("folio", sa.String(100), unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("registered_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('draft', 'paid')", name="ck_historical_status"),
        sa.CheckConstraint(
            "(status = 'draft' AND registered_at IS NULL AND folio IS NULL) OR "
            "(status = 'paid' AND registered_at IS NOT NULL AND folio IS NOT NULL)",
            name="ck_historical_registration",
        ),
    )
    op.create_index("ix_historical_requests_store_id", "historical_requests", ["store_id"])
    op.create_index(
        "ix_historical_requests_created_by_user_id", "historical_requests", ["created_by_user_id"]
    )
    op.create_index(
        "uq_historical_open_draft",
        "historical_requests",
        ["store_id", "created_by_user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )
    op.create_table(
        "historical_expenses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("historical_requests.id"), nullable=False),
        sa.Column("client_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("spent_on", sa.Date(), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("document_type", sa.String(20), nullable=False),
        sa.Column("cfdi_uuid", sa.String(36)),
        sa.Column("notes", sa.Text()),
        sa.Column("fiscal_data", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
    )
    for name in ("request_id", "spent_on", "cfdi_uuid"):
        op.create_index(f"ix_historical_expenses_{name}", "historical_expenses", [name])
    op.create_index(
        "uq_historical_active_uuid",
        "historical_expenses",
        ["cfdi_uuid"],
        unique=True,
        postgresql_where=sa.text("removed_at IS NULL AND cfdi_uuid IS NOT NULL"),
        sqlite_where=sa.text("removed_at IS NULL AND cfdi_uuid IS NOT NULL"),
    )
    op.create_table(
        "historical_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("expense_id", sa.Uuid(), sa.ForeignKey("historical_expenses.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("ocr_data", sa.JSON()),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "expense_id", "checksum_sha256", name="uq_historical_attachment_checksum"
        ),
    )
    op.create_index(
        "ix_historical_attachments_expense_id", "historical_attachments", ["expense_id"]
    )


def downgrade() -> None:
    for table in ("historical_attachments", "historical_expenses", "historical_requests"):
        op.drop_table(table)
