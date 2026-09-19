from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

from app.core.config import Settings

PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000


class InvalidToken(ValueError):
    pass


class CognitoConfigurationError(ValueError):
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


def parse_cognito_token(token: str, settings: Settings) -> str:
    if not settings.cognito_enabled:
        raise InvalidToken("Cognito authentication is disabled")
    if not settings.cognito_issuer or not settings.cognito_app_client_id:
        raise CognitoConfigurationError(
            "Cognito requires cognito_issuer and cognito_app_client_id"
        )

    try:
        import jwt
    except ImportError as exc:  # pragma: no cover - dependency configuration
        raise CognitoConfigurationError(
            "PyJWT is required when Cognito authentication is enabled"
        ) from exc

    jwks_url = settings.cognito_jwks_url or f"{settings.cognito_issuer}/.well-known/jwks.json"
    try:
        signing_key = _cognito_jwk_client(jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.cognito_issuer,
            options={"verify_aud": False},
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidToken("Invalid Cognito token") from exc

    if payload.get("token_use") not in {"access", "id"}:
        raise InvalidToken("Invalid Cognito token use")
    if payload.get("client_id") != settings.cognito_app_client_id and payload.get(
        "aud"
    ) != settings.cognito_app_client_id:
        raise InvalidToken("Cognito token is for a different app client")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidToken("Cognito token has no subject")
    return subject


@lru_cache(maxsize=8)
def _cognito_jwk_client(jwks_url: str):
    from jwt import PyJWKClient

    return PyJWKClient(jwks_url)


def _sign(data: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), data, hashlib.sha256).digest()
    return _b64encode(digest)


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")
