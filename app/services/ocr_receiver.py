import re
import unicodedata
from typing import Any

MAX_RECEIVER_DIFFERENCES = 3


def assess_invoice_receiver(
    raw_text: str | None,
    *,
    expected_name: str | None,
    expected_rfc: str | None,
) -> dict[str, Any]:
    text = _plain_text(raw_text or "")
    positions = [index for index, char in enumerate(text) if char.isascii() and char.isalnum()]
    compact_text = "".join(text[index] for index in positions)
    tokens = list(re.finditer(r"[A-Z0-9]+", text))
    fields = {
        "razon_social": _search_field(expected_name, text, compact_text, positions, tokens),
        "rfc": _search_field(expected_rfc, text, compact_text, positions, tokens),
    }
    missing_fields = [field for field, result in fields.items() if not result["accepted"]]
    return {
        "max_differences": MAX_RECEIVER_DIFFERENCES,
        "scope": "global",
        "accepted": not missing_fields,
        "missing_fields": missing_fields,
        "fields": fields,
    }


def _search_field(
    expected: str | None,
    text: str,
    compact_text: str,
    positions: list[int],
    tokens: list[re.Match[str]],
) -> dict[str, Any]:
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

    exact = compact_text.find(normalized_expected)
    if exact >= 0:
        start = positions[exact]
        end = positions[exact + len(normalized_expected) - 1] + 1
        distance = 0
    else:
        start, end = 0, 0
        distance = MAX_RECEIVER_DIFFERENCES + 1
        best_key = (distance, len(normalized_expected))
        minimum = max(1, len(normalized_expected) - MAX_RECEIVER_DIFFERENCES)
        maximum = len(normalized_expected) + MAX_RECEIVER_DIFFERENCES
        label_starts = {match.start() for match in re.finditer(r"[A-Z0-9]+[ \t]*:", text)}
        # Search consecutive complete tokens everywhere, without requiring field labels.
        # Do not consume a following label or truncate a mismatching token.
        for index, first in enumerate(tokens):
            candidate = ""
            for last_index in range(index, len(tokens)):
                last = tokens[last_index]
                if last.start() in label_starts:
                    break
                candidate += last[0]
                if len(candidate) > maximum:
                    break
                if len(candidate) < minimum:
                    continue
                candidate_distance = _edit_distance(
                    normalized_expected, candidate, MAX_RECEIVER_DIFFERENCES,
                )
                key = (candidate_distance, abs(len(candidate) - len(normalized_expected)))
                if candidate_distance <= MAX_RECEIVER_DIFFERENCES and key < best_key:
                    best_key = key
                    distance = candidate_distance
                    start, end = first.start(), last.end()
        if not end:
            return result

    detected = " ".join(text[start:end].split())
    return {
        **result,
        "detected": detected,
        "normalized_detected": _compact(detected),
        "edit_distance": distance,
        "match_type": "exact" if distance == 0 else "tolerated",
        "accepted": True,
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
