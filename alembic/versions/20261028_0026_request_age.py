"""Preserve the first submission and definitive rejection dates."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261028_0026"
down_revision: str | None = "20261016_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("reimbursement_requests")
    }
    for name in ("first_submitted_at", "rejected_at"):
        if name not in columns:
            op.add_column(
                "reimbursement_requests", sa.Column(name, sa.DateTime(timezone=True), nullable=True),
            )

    requests = sa.table(
        "reimbursement_requests", sa.column("id"), sa.column("first_submitted_at"),
        sa.column("rejected_at"),
    )
    events = sa.table(
        "audit_logs", sa.column("reimbursement_request_id"), sa.column("action"),
        sa.column("to_status"), sa.column("created_at"),
    )
    for column, status in (("first_submitted_at", "submitted"), ("rejected_at", "rejected")):
        first_event = sa.select(sa.func.min(events.c.created_at)).where(
            events.c.reimbursement_request_id == requests.c.id,
            events.c.action.in_(("request_status_changed", "dev_hud_request_status_changed")),
            events.c.to_status == status,
        ).scalar_subquery()
        op.execute(
            requests.update().where(requests.c[column].is_(None)).values({column: first_event})
        )


def downgrade() -> None:
    with op.batch_alter_table("reimbursement_requests") as batch:
        batch.drop_column("rejected_at")
        batch.drop_column("first_submitted_at")
