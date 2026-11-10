"""Replace UUID-based archive folios with independent daily sequences.

Revision ID: 20261103_0028
Revises: 20261103_0027
"""

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa

from alembic import op

revision = "20261103_0028"
down_revision = "20261103_0027"
branch_labels = None
depends_on = None

requests = sa.table(
    "historical_requests",
    sa.column("id", sa.Uuid()),
    sa.column("store_id", sa.Uuid()),
    sa.column("status", sa.String()),
    sa.column("folio", sa.String()),
    sa.column("registered_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
)
stores = sa.table("stores", sa.column("id", sa.Uuid()), sa.column("code", sa.String()))
logs = sa.table(
    "audit_logs",
    sa.column("id", sa.Uuid()),
    sa.column("actor_type", sa.Enum("system", "user", name="audit_actor_type")),
    sa.column("action", sa.String()),
    sa.column("message", sa.Text()),
    sa.column("payload", sa.JSON()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


def _record_change(connection, row, before, after, *, restoring=False):
    connection.execute(requests.update().where(requests.c.id == row.id).values(folio=after))
    connection.execute(
        logs.insert().values(
            id=uuid4(),
            actor_type="system",
            action="historical_folio_restored" if restoring else "historical_folio_updated",
            message=f"Cambio de folio extemporaneo de {before} a {after}.",
            payload={
                "historical_request_id": str(row.id),
                "store_id": str(row.store_id),
                "store_code": row.code,
                "request_folio": after,
                "previous_folio": before,
                "new_folio": after,
                "actor_name": "Sistema",
                "actor_role": "system",
                "es_extemporaneo": True,
                "migration": revision,
            },
            created_at=datetime.now(UTC),
        )
    )


def upgrade():
    connection = op.get_bind()
    rows = list(
        connection.execute(
            sa.select(
                requests.c.id,
                requests.c.store_id,
                requests.c.folio,
                requests.c.registered_at,
                stores.c.code,
            )
            .join(stores, stores.c.id == requests.c.store_id)
            .where(
                requests.c.status == "paid",
            )
            .order_by(requests.c.registered_at, requests.c.created_at, requests.c.id)
        )
    )
    counters = {}
    legacy = []
    for row in rows:
        numbered = re.fullmatch(r"(E-.+-[0-9]{8})([0-9]+)", row.folio or "")
        original = re.fullmatch(r"(E-.+-[0-9]{8})-([0-9A-Fa-f]{32})", row.folio or "")
        if numbered:
            prefix, suffix = numbered.groups()
            counters[prefix] = max(counters.get(prefix, 0), int(suffix))
        elif original and original.group(2).lower() == row.id.hex:
            legacy.append((row, original.group(1)))
    for row, prefix in legacy:
        counters[prefix] = counters.get(prefix, 0) + 1
        _record_change(connection, row, row.folio, f"{prefix}{counters[prefix]}")


def downgrade():
    connection = op.get_bind()
    events = list(
        connection.execute(
            sa.select(logs.c.payload).where(
                logs.c.action == "historical_folio_updated",
            )
        )
    )
    for event in events:
        payload = event.payload or {}
        if payload.get("migration") != revision:
            continue
        identifier = UUID(payload["historical_request_id"])
        row = connection.execute(
            sa.select(
                requests.c.id,
                requests.c.store_id,
                requests.c.folio,
                stores.c.code,
            )
            .join(stores, stores.c.id == requests.c.store_id)
            .where(
                requests.c.id == identifier,
            )
        ).first()
        if row is not None and row.folio == payload["new_folio"]:
            _record_change(connection, row, row.folio, payload["previous_folio"], restoring=True)
