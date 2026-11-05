from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
from datetime import date
from decimal import Decimal
from typing import Any


def build_ocr_preview_payload(
    *,
    checksum_sha256: str,
    suggested_cfdi_uuid: str | None,
    extracted_total: Decimal | None,
    extracted_date: date | None,
    extracted_supplier: str | None,
    confidence: Decimal | None,
) -> dict[str, Any]:
    return {
        "checksum_sha256": checksum_sha256,
        "suggested_cfdi_uuid": suggested_cfdi_uuid,
        "extracted_total": str(extracted_total) if extracted_total is not None else None,
        "extracted_date": extracted_date.isoformat() if extracted_date is not None else None,
        "extracted_supplier": extracted_supplier,
        "confidence": str(confidence) if confidence is not None else None,
    }


def sign_ocr_preview_payload(payload: dict[str, Any], secret: str) -> str:
    payload_bytes = _payload_bytes(payload)
    body = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"v1.{body}.{signature}"


def verify_ocr_preview_token(token: str | None, secret: str) -> dict[str, Any] | None:
    if not token:
        return None

    try:
        version, body, signature = token.split(".", maxsplit=2)
    except (ValueError, binascii.Error):
        return None

    if version != "v1":
        return None

    try:
        payload_bytes = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    except (ValueError, binascii.Error):
        return None

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _payload_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
