from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CfdiParseResult(BaseModel):
    version: str | None = None
    uuid: str | None = None
    issuer_rfc: str | None = None
    issuer_name: str | None = None
    receiver_rfc: str | None = None
    receiver_name: str | None = None
    total: Decimal | None = None
    currency: str | None = None
    issued_at: datetime | None = None
    payment_method: str | None = None
    warnings: list[str] = Field(default_factory=list)


class CfdiValidationIssue(BaseModel):
    code: str
    message: str
    severity: str = "error"


class CfdiValidationResult(BaseModel):
    is_valid: bool
    parsed: CfdiParseResult
    issues: list[CfdiValidationIssue] = Field(default_factory=list)


class CfdiUuidAvailability(BaseModel):
    uuid: str
    is_available: bool
    existing_expense_id: UUID | None = None
    existing_validation_expense_id: UUID | None = None


class CfdiValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    expense_id: UUID
    attachment_id: UUID
    uuid: str | None = None
    issuer_rfc: str | None = None
    receiver_rfc: str | None = None
    total: Decimal | None = None
    currency: str | None = None
    issued_at: datetime | None = None
    is_valid: bool
    issues: list[dict[str, Any]] = Field(default_factory=list)
    checksum_sha256: str
    validator_version: str
    is_current: bool
    validated_at: datetime
