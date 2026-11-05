from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def lock_fiscal_uuid(db: Session, uuid: str) -> None:
    # Two independent archives cannot share a UNIQUE constraint. Serialize claims
    # for the same fiscal UUID across the normal and informational write paths.
    if db.get_bind().dialect.name == "postgresql":
        key = int.from_bytes(sha256(uuid.upper().encode("ascii")).digest()[:8], "big", signed=True)
        db.execute(select(func.pg_advisory_xact_lock(key)))
