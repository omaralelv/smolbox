from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from app.core.config import Settings

SUPPORTED_TEXTRACT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}
SPANISH_MONTH_NUMBERS = {
    "ENE": 1,
    "ENERO": 1,
    "FEB": 2,
    "FEBRERO": 2,
    "MAR": 3,
    "MARZO": 3,
    "ABR": 4,
    "ABRIL": 4,
    "MAY": 5,
    "MAYO": 5,
    "JUN": 6,
    "JUNIO": 6,
    "JUL": 7,
    "JULIO": 7,
    "AGO": 8,
    "AGOSTO": 8,
    "SEP": 9,
    "SEPT": 9,
    "SEPTIEMBRE": 9,
    "SET": 9,
    "SETIEMBRE": 9,
    "OCT": 10,
    "OCTUBRE": 10,
    "NOV": 11,
    "NOVIEMBRE": 11,
    "DIC": 12,
    "DICIEMBRE": 12,
}
SPANISH_MONTH_PATTERN = "|".join(
    sorted((re.escape(month) for month in SPANISH_MONTH_NUMBERS), key=len, reverse=True)
)
DATE_CONTEXT_HINTS = (
    "FECHADEEMISION",
    "FECHAEMISION",
    "FECHADEEXPEDICION",
    "FECHAEXPEDICION",
    "FECHAFACTURA",
    "EXPEDIDO",
    "EMISION",
    "FECHA",
)
DEPRIORITIZED_DATE_CONTEXT_HINTS = (
    "CERTIFICACION",
    "TIMBRADO",
    "VENCIMIENTO",
    "PAGO",
    "PAGADO",
    "CERTIFICADO",
)

OCR_UNREADABLE_DOCUMENT_MESSAGE = (
    "No se pudo leer el documento con OCR.\n"
    "El archivo cargado no tiene un formato compatible o no puede ser procesado.\n"
    "Por favor, carga nuevamente el archivo en formato PDF válido."
)
OCR_RECEIVER_MISMATCH_CODE = "OCR_RECEIVER_MISMATCH"


class TextractOcrError(RuntimeError):
    pass


@dataclass(frozen=True)
class TextractOcrResult:
    raw_text: str
    extracted_total: Decimal | None
    extracted_date: date | None
    extracted_supplier: str | None
    suggested_cfdi_uuid: str | None
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
            if _is_textract_document_read_error(exc):
                fallback_result = _extract_text_pdf_expense(content, content_type=content_type)
                if fallback_result is not None:
                    return fallback_result
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


def validate_expected_invoice_receiver(
    raw_text: str | None,
    *,
    expected_name: str | None,
    expected_rfc: str | None,
) -> list[str]:
    missing_fields: list[str] = []
    searchable_text = _compact_search_text(raw_text)

    if expected_name and _compact_search_text(expected_name) not in searchable_text:
        missing_fields.append("razon_social")

    if expected_rfc and _compact_search_text(expected_rfc) not in searchable_text:
        missing_fields.append("rfc")

    return missing_fields


def expected_invoice_receiver_message(
    missing_fields: list[str],
    *,
    expected_name: str | None,
    expected_rfc: str | None,
) -> str:
    missing_labels = {
        "razon_social": "Razón Social",
        "rfc": "RFC",
    }
    missing_text = ", ".join(missing_labels[field] for field in missing_fields)
    expected_values = [
        f"Razón Social: {expected_name}" if expected_name else "",
        f"RFC: {expected_rfc}" if expected_rfc else "",
    ]
    return "\n".join(
        [
            "La factura PDF no corresponde al receptor esperado.",
            f"Corroborar: {missing_text}.",
            f"Debe incluir {' y '.join(value for value in expected_values if value)}.",
        ]
    )


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
    extracted_date = _date_from_summary_or_text(values_by_type, raw_text)
    suggested_cfdi_uuid = _cfdi_uuid_from_text(raw_text)
    confidence = _average_confidence(summary_fields)

    return TextractOcrResult(
        raw_text=raw_text,
        extracted_total=total,
        extracted_date=extracted_date,
        extracted_supplier=supplier,
        suggested_cfdi_uuid=suggested_cfdi_uuid,
        confidence=confidence,
        raw_response=response if store_raw_response else None,
    )


def _compact_search_text(value: str | None) -> str:
    if not value:
        return ""
    without_accents = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9]", "", without_accents.upper())


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


def _extract_text_pdf_expense(
    content: bytes,
    *,
    content_type: str,
) -> TextractOcrResult | None:
    if content_type.lower().split(";", maxsplit=1)[0] != "application/pdf":
        return None

    raw_text = _pdf_text_from_bytes(content)
    if not raw_text:
        return None

    return TextractOcrResult(
        raw_text=raw_text,
        extracted_total=_total_from_ocr_text(raw_text),
        extracted_date=_date_from_summary_or_text({}, raw_text),
        extracted_supplier=None,
        suggested_cfdi_uuid=_cfdi_uuid_from_text(raw_text),
        confidence=None,
        raw_response=None,
    )


def _pdf_text_from_bytes(content: bytes) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency is installed in packaged app
        return None

    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            return None

        text_parts = [
            text
            for page in reader.pages
            if (text := (page.extract_text() or "").strip())
        ]
    except Exception:  # noqa: BLE001
        return None

    raw_text = "\n".join(text_parts).strip()
    return raw_text or None


def _money_from_text(value: str | None) -> Decimal | None:
    if not value:
        return None
    values = _money_values_from_text(value)
    if not values:
        return None
    return values[0]


def _total_from_ocr_text(raw_text: str | None) -> Decimal | None:
    if not raw_text:
        return None

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if not _is_total_label_line(line):
            continue

        line_values = _money_values_from_text(line)
        if line_values:
            return line_values[-1]

        nearby_values: list[Decimal] = []
        for nearby_line in lines[index + 1 : index + 12]:
            if _looks_like_new_section_after_total(nearby_line):
                break
            nearby_values.extend(_money_values_from_text(nearby_line))

        if nearby_values:
            return nearby_values[-1]

    return None


def _money_values_from_text(value: str) -> list[Decimal]:
    matches = re.finditer(r"-?\$?\s*\d[\d,]*(?:\.\d{1,2})?", value)
    values: list[Decimal] = []
    for match in matches:
        normalized = match.group(0).replace("$", "").replace(",", "").replace(" ", "")
        try:
            values.append(Decimal(normalized).quantize(Decimal("0.01")))
        except InvalidOperation:
            continue
    return values


def _is_total_label_line(value: str) -> bool:
    compact = _compact_search_text(value)
    return "TOTAL" in compact and "SUBTOTAL" not in compact


def _looks_like_new_section_after_total(value: str) -> bool:
    compact = _compact_search_text(value)
    return compact.startswith(
        (
            "PAGINA",
            "SELLO",
            "CADENAORIGINAL",
        )
    )


def _is_textract_document_read_error(exc: Exception) -> bool:
    error_text = f"{exc.__class__.__name__} {exc}".lower()
    return (
        "unsupported document" in error_text
        or "unsupporteddocument" in error_text
        or "bad document" in error_text
        or "baddocument" in error_text
    )


def _date_from_summary_or_text(
    values_by_type: dict[str, list[str]],
    raw_text: str,
) -> date | None:
    for field_type in ("INVOICE_RECEIPT_DATE", "DATE"):
        for value in values_by_type.get(field_type, []):
            parsed = _date_from_text(value)
            if parsed is not None:
                return parsed

    return _date_from_ocr_text(raw_text)


def _date_from_ocr_text(raw_text: str | None) -> date | None:
    if not raw_text:
        return None

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[tuple[int, int, date]] = []

    for index, line in enumerate(lines):
        parsed = _date_from_text(line)
        if parsed is not None:
            candidates.append((_date_context_rank(line), index, parsed))

        if index + 1 < len(lines) and _has_date_context(line):
            parsed_next = _date_from_text(f"{line} {lines[index + 1]}")
            if parsed_next is not None:
                candidates.append((_date_context_rank(line), index, parsed_next))

    if not candidates:
        return None

    return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def _date_from_text(value: str | None) -> date | None:
    if not value:
        return None

    normalized = re.sub(r"\s+", " ", value.strip())
    normalized_without_accents = _text_without_accents(normalized).upper()

    month_match = re.search(
        rf"\b(\d{{1,2}})(?:\s+|[-/])(?:DE\s+)?({SPANISH_MONTH_PATTERN})(?:\s+|[-/])(?:DE\s+)?(\d{{2,4}})\b",
        normalized_without_accents,
    )
    if month_match:
        day = int(month_match.group(1))
        month = SPANISH_MONTH_NUMBERS[month_match.group(2)]
        year = _normalize_year(int(month_match.group(3)))
        return _safe_date(year, month, day)

    iso_match = re.search(
        r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[T\s]\d{1,2}:\d{2}(?::\d{2})?)?\b",
        normalized,
    )
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
        return _safe_date(year, month, day)

    short_match = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b", normalized)
    if not short_match:
        return None

    first, second, year = (int(part) for part in short_match.groups())
    year = _normalize_year(year)
    return _safe_date(year, second, first) or _safe_date(year, first, second)


def _date_context_rank(value: str) -> int:
    compact = _compact_search_text(value)
    has_positive_context = any(hint in compact for hint in DATE_CONTEXT_HINTS)
    has_deprioritized_context = any(
        hint in compact for hint in DEPRIORITIZED_DATE_CONTEXT_HINTS
    )

    if has_positive_context and not has_deprioritized_context:
        return 0
    if not has_deprioritized_context:
        return 1
    return 2


def _has_date_context(value: str) -> bool:
    compact = _compact_search_text(value)
    return any(hint in compact for hint in DATE_CONTEXT_HINTS)


def _text_without_accents(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def _normalize_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year < 70 else 1900 + year
    return year


def _cfdi_uuid_from_text(value: str | None) -> str | None:
    if not value:
        return None

    normalized = re.sub(r"\s*-\s*", "-", value)
    hyphenated_match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        normalized,
    )
    if hyphenated_match:
        return hyphenated_match.group(0).upper()

    compact_match = re.search(r"\b[0-9a-fA-F]{32}\b", normalized)
    if compact_match:
        return _format_compact_uuid(compact_match.group(0))

    label_match = re.search(
        r"(?:folio\s*fiscal|uuid|id\s*documento|timbre\s*fiscal)",
        normalized,
        flags=re.IGNORECASE,
    )
    if label_match:
        nearby_text = normalized[label_match.end() : label_match.end() + 160]
        nearby_uuid = _uuid_from_text_with_separators(nearby_text)
        if nearby_uuid:
            return nearby_uuid

    return _uuid_from_text_with_separators(normalized)


def _uuid_from_text_with_separators(value: str) -> str | None:
    match = re.search(r"(?<![0-9a-fA-F])((?:[0-9a-fA-F][\s-]*){32})(?![0-9a-fA-F])", value)
    if not match:
        return None

    compact = re.sub(r"[^0-9a-fA-F]", "", match.group(1))
    if len(compact) != 32:
        return None

    return _format_compact_uuid(compact)


def _format_compact_uuid(value: str) -> str:
    compact = value.upper()
    return "-".join(
        (
            compact[:8],
            compact[8:12],
            compact[12:16],
            compact[16:20],
            compact[20:],
        )
    )


def _safe_date(year: int, month: int, day: int) -> date | None:
    if year < 1900 or year > 2100:
        return None
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
