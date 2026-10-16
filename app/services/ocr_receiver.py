import re
import unicodedata
from typing import Any

MAX_RECEIVER_DIFFERENCES = 3

_ROLE = re.compile(
    r"\b(?:(?P<field>R[.\s]*F[.\s]*C\.?|RAZON\s+SOCIAL|NOMBRE)\s+(?:DEL\s+)?"
    r"(?P<field_role>RECEPTOR|EMISOR)\b|(?P<heading>RECEPTOR|EMISOR)\b"
    r"|(?P<client>(?:DATOS\s+DEL\s+)?CLIENTE)(?=\s*:|\s*$))", re.MULTILINE,
)
_FIELD = re.compile(
    r"\b(?:(?P<razon_social>RAZON\s+SOCIAL|NOMBRE(?:\s+O\s+RAZON\s+SOCIAL)?"
    r"|DENOMINACION(?:\s+O\s+RAZON\s+SOCIAL)?)"
    r"|(?P<rfc>R[.\s]*F[.\s]*C\.?)"
    r"|(?P<other>DOMICILIO|DIRECCION|REGIMEN\s+FISCAL|USO\s+(?:DEL\s+)?CFDI"
    r"|CODIGO\s+POSTAL|C\.?\s*P\.?|FECHA|FOLIO(?:\s+FISCAL)?|TOTAL|SUBTOTAL"
    r"|MONEDA|CORREO|TELEFONO|LUGAR\s+DE\s+EXPEDICION))\b",
)
_BODY = re.compile(r"\b(?:CONCEPTOS|SUBTOTAL|FOLIO\s+FISCAL)\b")
_ADDRESS_START = re.compile(
    r"(?:^|(?<=[;|\t])|(?<=  ))[ \t]*"
    r"\b(?:AV(?:ENIDA)?|CALLE|CALZ(?:ADA)?|BLVD|BOULEVARD|BULEVAR"
    r"|PROL(?:ONGACION)?|CARR(?:ETERA)?|PRIV(?:ADA)?|PASEO|CIRCUITO|ANDADOR)\b\.?[ \t]+"
    r"(?=[^\r\n]{0,160}(?:\b\d+[A-Z]?\b|\bS[ \t]*/[ \t]*N\b))",
    re.MULTILINE,
)
_NON_IDENTITY_ROLE_PREFIX = re.compile(
    r"\b(?:DOMICILIO(?:\s+FISCAL)?|DIRECCION(?:\s+FISCAL)?|REGIMEN\s+FISCAL"
    r"|USO\s+(?:DEL\s+)?CFDI)(?:\s+(?:DEL|DE|POR|EL))*\s*$",
)


def assess_invoice_receiver(
    raw_text: str | None,
    *,
    expected_name: str | None,
    expected_rfc: str | None,
) -> dict[str, Any]:
    text = _plain_text(raw_text or "")
    sections, scope = _receiver_sections(text)
    assessments = []
    for section in sections or [""]:
        section = _BODY.split(section, maxsplit=1)[0]
        candidates = _field_candidates(section, expected_name, expected_rfc)
        if scope == "unlabeled":
            for field in candidates:
                labels = [label for label in _FIELD.finditer(section) if label.lastgroup == field]
                if len(labels) > 1 and len({_compact(value) for value in candidates[field]}) > 1:
                    candidates = {"razon_social": [], "rfc": []}
                    scope = "ambiguous"
                    break
        fields = {
            "razon_social": _compare_field(expected_name, candidates["razon_social"]),
            "rfc": _compare_field(expected_rfc, candidates["rfc"]),
        }
        missing_fields = [field for field, result in fields.items() if not result["accepted"]]
        assessments.append({
            "max_differences": MAX_RECEIVER_DIFFERENCES,
            "scope": scope,
            "accepted": not missing_fields,
            "missing_fields": missing_fields,
            "fields": fields,
        })
    # Do not combine a name from one receiver with an RFC from another receiver.
    return min(assessments, key=lambda item: (
        len(item["missing_fields"]),
        sum(field["edit_distance"] if field["edit_distance"] is not None else 4
            for field in item["fields"].values()),
    ))


def _receiver_sections(text: str) -> tuple[list[str], str]:
    roles = [token for token in _ROLE.finditer(text) if not _is_non_identity_role(text, token)]
    if not roles:
        return [text], "unlabeled"
    sections = []
    parts: list[str] = []
    current_role = None
    for index, token in enumerate(roles):
        role = token["field_role"] or token["heading"] or "RECEPTOR"
        if index and token["field"] is None and roles[index - 1]["field"] is None:
            previous_role = roles[index - 1]["heading"] or "RECEPTOR"
            between = text[roles[index - 1].end():token.start()]
            if role != previous_role and not between.strip(" \t:/|-") and "\n" not in between:
                role = "AMBIGUOUS"
        # Consecutive "Nombre del receptor" and "RFC del receptor" are one block.
        if role != current_role or token["field"] is None:
            if current_role == "RECEPTOR":
                sections.append("\n".join(parts))
            parts = []
        current_role = role
        stop = roles[index + 1].start() if index + 1 < len(roles) else len(text)
        label = f"{token['field']}: " if token["field"] else ""
        parts.append(label + text[token.end():stop])
    if current_role == "RECEPTOR":
        sections.append("\n".join(parts))
    return sections, "receiver" if sections else "no_receiver"


def _is_non_identity_role(text: str, token: re.Match[str]) -> bool:
    if token["field"]:
        return False
    line_start = text.rfind("\n", 0, token.start()) + 1
    return _NON_IDENTITY_ROLE_PREFIX.search(text[line_start:token.start()]) is not None


def _before_address(value: str) -> str:
    # Require a line/column boundary and address evidence, not just a street word in a name.
    address = _ADDRESS_START.search(value)
    return (value[:address.start()] if address else value).strip(" \t\r\n:=,;|")


def _field_candidates(
    section: str, expected_name: str | None, expected_rfc: str | None,
) -> dict[str, list[str]]:
    labels = list(_FIELD.finditer(section))
    values: dict[str, list[str]] = {"razon_social": [], "rfc": []}
    labeled_fields = set()
    for index, label in enumerate(labels):
        field = label.lastgroup
        if field not in values:
            continue
        labeled_fields.add(field)
        stop = labels[index + 1].start() if index + 1 < len(labels) else len(section)
        value = _before_address(section[label.end():stop])
        if not value:
            continue
        values[field].append(" ".join(value.split()))

    if "razon_social" not in labeled_fields:
        # Unlabeled company names normally precede the first labeled field.
        prefix = _before_address(section[:labels[0].start()] if labels else section)
        normalized_name = _compact(_plain_text(expected_name or ""))
        normalized_rfc = _compact(_plain_text(expected_rfc or ""))
        prefix = re.sub(
            r"\b[A-Z0-9]{9,15}\b",
            lambda match: "\n" if normalized_rfc
            and _edit_distance(normalized_rfc, match[0], MAX_RECEIVER_DIFFERENCES)
            <= MAX_RECEIVER_DIFFERENCES
            and _edit_distance(normalized_name, match[0], MAX_RECEIVER_DIFFERENCES)
            > MAX_RECEIVER_DIFFERENCES
            else match[0],
            prefix,
        )
        values["razon_social"].extend(
            value for value in _line_groups(prefix)
            if any(char.isalpha() for char in _compact(value))
        )
    if "rfc" not in labeled_fields:
        for line in section.splitlines():
            for value in [line, *re.findall(r"[A-Z0-9]+", line)]:
                compact = _compact(value)
                if any(char.isdigit() for char in compact) and any(char.isalpha() for char in compact):
                    values["rfc"].append(value)
    return values


def _line_groups(text: str) -> list[str]:
    lines = [line.strip(" \t:=,;|") for line in text.splitlines() if line.strip()]
    return [
        " ".join(lines[start:start + count])
        for start in range(len(lines))
        for count in range(1, min(3, len(lines) - start) + 1)
    ]


def _compare_field(expected: str | None, candidates: list[str]) -> dict[str, Any]:
    normalized_expected = _compact(_plain_text(expected or ""))
    result = {
        "expected": expected,
        "detected": None,
        "normalized_detected": None,
        "edit_distance": None,
        "match_type": "not_required" if not normalized_expected else "missing",
        "accepted": not normalized_expected,
    }
    if not normalized_expected:
        return result
    normalized_candidates = {
        _compact(candidate): candidate for candidate in candidates if _compact(candidate)
    }
    if not normalized_candidates:
        return result
    best = min(normalized_candidates, key=lambda candidate: _edit_distance(
        normalized_expected, candidate, MAX_RECEIVER_DIFFERENCES,
    ))
    distance = _edit_distance(normalized_expected, best, MAX_RECEIVER_DIFFERENCES)
    accepted = distance <= MAX_RECEIVER_DIFFERENCES
    return {
        **result,
        "detected": normalized_candidates[best],
        "normalized_detected": best,
        "edit_distance": distance if accepted else None,
        "match_type": "exact" if distance == 0 else "tolerated" if accepted else "mismatch",
        "accepted": accepted,
    }


def _edit_distance(expected: str, detected: str, limit: int) -> int:
    if abs(len(expected) - len(detected)) > limit:
        return limit + 1
    previous = list(range(len(detected) + 1))
    for row, expected_char in enumerate(expected, start=1):
        current = [row]
        for column, detected_char in enumerate(detected, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (expected_char != detected_char),
            ))
        if min(current) > limit:
            return limit + 1
        previous = current
    return min(previous[-1], limit + 1)


def _plain_text(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    ).upper()


def _compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value)
