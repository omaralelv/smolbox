from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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
