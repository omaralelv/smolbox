from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.config import Settings

SUPPORTED_TEXTRACT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


class TextractOcrError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextractOcrResult:
    raw_text: str
    extracted_total: Decimal | None
    extracted_date: date | None
    extracted_supplier: str | None
    confidence: Decimal | None
    raw_response: dict[str, Any] | None


class TextractOcrService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_enabled(self) -> bool:
        return self.settings.textract_enabled

    def supports_content_type(self, content_type: str) -> bool:
        return content_type.lower().split(";", maxsplit=1)[0] in SUPPORTED_TEXTRACT_CONTENT_TYPES

    def extract_expense(
        self,
        content: bytes,
        *,
        content_type: str,
        filename: str,
    ) -> TextractOcrResult | None:
        if not self.is_enabled or not self.supports_content_type(content_type):
            return None

        client = self._client()
        try:
            # Aqui vive la llamada real a AWS Textract.
            response = client.analyze_expense(Document={"Bytes": content})
        except Exception as exc:  # pragma: no cover - depends on AWS
            raise TextractOcrError(f"Textract failed for {filename}: {exc}") from exc

        return _parse_analyze_expense_response(
            response,
            store_raw_response=self.settings.textract_store_raw_response,
        )

    def _client(self):
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - only happens without dependency installed
            raise TextractOcrError(
                "boto3 is not installed. Install project dependencies before enabling Textract."
            ) from exc

        session_kwargs: dict[str, str] = {"region_name": self.settings.aws_region}
        if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = self.settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = self.settings.aws_secret_access_key
        if self.settings.aws_session_token:
            session_kwargs["aws_session_token"] = self.settings.aws_session_token

        return boto3.Session(**session_kwargs).client("textract")


def _parse_analyze_expense_response(
    response: dict[str, Any],
    *,
    store_raw_response: bool,
) -> TextractOcrResult:
    expense_documents = response.get("ExpenseDocuments") or []
    first_document = expense_documents[0] if expense_documents else {}
    summary_fields = first_document.get("SummaryFields") or []

    values_by_type = _summary_values_by_type(summary_fields)
    raw_text = _raw_text_from_response(response)

    total = _money_from_text(
        _first_summary_value(values_by_type, "TOTAL", "AMOUNT_DUE", "GRAND_TOTAL")
    )
    supplier = _first_summary_value(values_by_type, "VENDOR_NAME", "NAME")
    extracted_date = _date_from_text(
        _first_summary_value(values_by_type, "INVOICE_RECEIPT_DATE", "DATE")
    )
    confidence = _average_confidence(summary_fields)

    return TextractOcrResult(
        raw_text=raw_text,
        extracted_total=total,
        extracted_date=extracted_date,
        extracted_supplier=supplier,
        confidence=confidence,
        raw_response=response if store_raw_response else None,
    )


def _summary_values_by_type(summary_fields: list[dict[str, Any]]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for field in summary_fields:
        field_type = str((field.get("Type") or {}).get("Text") or "").upper().strip()
        value = str((field.get("ValueDetection") or {}).get("Text") or "").strip()
        if field_type and value:
            values.setdefault(field_type, []).append(value)
    return values


def _first_summary_value(values_by_type: dict[str, list[str]], *field_types: str) -> str | None:
    for field_type in field_types:
        values = values_by_type.get(field_type)
        if values:
            return values[0]
    return None


def _raw_text_from_response(response: dict[str, Any]) -> str:
    text_parts: list[str] = []
    for document in response.get("ExpenseDocuments") or []:
        for block in document.get("Blocks") or []:
            if block.get("BlockType") == "LINE" and block.get("Text"):
                text_parts.append(str(block["Text"]))
        for field in document.get("SummaryFields") or []:
            value = (field.get("ValueDetection") or {}).get("Text")
            if value:
                text_parts.append(str(value))
    return "\n".join(dict.fromkeys(text_parts))


def _money_from_text(value: str | None) -> Decimal | None:
    if not value:
        return None
    match = re.search(r"-?\d[\d,]*(?:\.\d{1,2})?", value)
    if not match:
        return None
    try:
        return Decimal(match.group(0).replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _date_from_text(value: str | None) -> date | None:
    if not value:
        return None

    normalized = value.strip()
    iso_match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", normalized)
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
        return _safe_date(year, month, day)

    short_match = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", normalized)
    if not short_match:
        return None

    first, second, year = (int(part) for part in short_match.groups())
    return _safe_date(year, second, first) or _safe_date(year, first, second)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _average_confidence(summary_fields: list[dict[str, Any]]) -> Decimal | None:
    confidences: list[Decimal] = []
    for field in summary_fields:
        confidence = (field.get("ValueDetection") or {}).get("Confidence")
        if confidence is None:
            continue
        try:
            confidences.append(Decimal(str(confidence)))
        except InvalidOperation:
            continue

    if not confidences:
        return None

    return (sum(confidences) / Decimal(len(confidences))).quantize(Decimal("0.01"))
