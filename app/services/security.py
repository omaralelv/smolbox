from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import Settings

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000


class InvalidToken(ValueError):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        PASSWORD_ITERATIONS,
    )
    return (
        f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, iterations_raw, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_raw)
        expected = bytes.fromhex(digest_hex)
        salt = bytes.fromhex(salt_hex)
    except (TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_access_token(user_id: UUID, settings: Settings) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "exp": int(expires_at.timestamp()),
    }
    payload_part = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(payload_part.encode(), settings.auth_token_secret)
    return f"{payload_part}.{signature}", expires_at


def parse_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError as exc:
        raise InvalidToken("Malformed token") from exc

    expected_signature = _sign(payload_part.encode(), settings.auth_token_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidToken("Invalid token signature")

    try:
        payload = json.loads(_b64decode(payload_part))
        expires_at = int(payload["exp"])
        user_id = UUID(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidToken("Invalid token payload") from exc

    if datetime.now(UTC).timestamp() > expires_at:
        raise InvalidToken("Expired token")
    return user_id


def _sign(data: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), data, hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")
