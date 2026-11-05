"""Optional document positions; these never participate in fiscal validation."""

import re
from ctypes import byref, c_int
from dataclasses import asdict, replace
from math import isfinite

from app.services.ocr_folio import FolioRegion
from app.services.pdf_ocr import _PDFIUM_LOCK, MAX_PDF_OCR_PAGES, find_pdf_folio_rectangle
from app.services.textract_ocr import (
    SPANISH_MONTH_PATTERN,
    TextractOcrResult,
    _date_context_rank,
    _date_from_text,
    _is_total_label_line,
    _money_from_text,
)

_DATES = re.compile(
    rf"\b(?:\d{{4}}[-/.]\d{{1,2}}[-/.]\d{{1,2}}(?:T\d{{2}}:\d{{2}}(?::\d{{2}})?)?"
    rf"|\d{{1,2}}[-/.]\d{{1,2}}[-/.]\d{{2,4}}"
    rf"|\d{{1,2}}(?:\s+|[-/])(?:de\s+)?(?:{SPANISH_MONTH_PATTERN})(?:\s+|[-/])(?:de\s+)?\d{{2,4}})(?!\d)",
    re.IGNORECASE,
)
_MONEY = re.compile(r"(?<![\w.])-?\$?\s*\d[\d,]*(?:\.\d{1,2})?(?![\d.])")
_BARE_MONEY = re.compile(
    r"(?:MXN|M\.?N\.?|\$)?\s*-?\d[\d,]*(?:\.\d{1,2})?\s*(?:MXN|M\.?N\.?|PESOS)?", re.IGNORECASE
)


def build_document_highlights(
    content: bytes, result: TextractOcrResult, *, include_folio: bool
) -> list[dict]:
    import pypdfium2 as pdfium

    with _PDFIUM_LOCK:
        document = pdfium.PdfDocument(content)
        try:
            count = len(document)
            if not 1 <= count <= MAX_PDF_OCR_PAGES:
                return []
            chosen = {}
            if include_folio and result.suggested_cfdi_uuid:
                chosen["folio"] = _resolve_page(result.folio_region, count)
            for field, value in (
                ("date", result.extracted_date),
                ("total", result.extracted_total),
            ):
                if value is not None:
                    chosen[field] = _ocr_region(result.geometry_blocks, field, value, count)
            missing = {field for field, region in chosen.items() if region is None}
            candidates = {field: [] for field in missing}
            for index in range(count) if missing else ():
                page = document[index]
                try:
                    if "folio" in missing:
                        box = find_pdf_folio_rectangle(
                            page, result.suggested_cfdi_uuid.replace("-", "").upper()
                        )
                        region = _pdf_region(page, box, index + 1) if box is not None else None
                        if region is not None:
                            candidates["folio"].append((0, region))
                    if missing - {"folio"}:
                        text_page = page.get_textpage()
                        try:
                            lines = [
                                line.strip()
                                for line in text_page.get_text_range().splitlines()
                                if line.strip()
                            ]
                            for field in missing - {"folio"}:
                                value = (
                                    result.extracted_date
                                    if field == "date"
                                    else result.extracted_total
                                )
                                for rank, token, line in _candidates(lines, field, value):
                                    candidates[field].extend(
                                        (rank, region)
                                        for region in _pdf_token_regions(
                                            page, text_page, token, line, index + 1
                                        )
                                    )
                        finally:
                            text_page.close()
                finally:
                    page.close()
            for field in missing:
                chosen[field] = _unique_region(candidates[field])
            return [
                {"field": field, **asdict(region)}
                for field, region in chosen.items()
                if region is not None
            ]
        finally:
            document.close()


def _resolve_page(region: FolioRegion | None, count: int) -> FolioRegion | None:
    if region is None or not region.is_valid():
        return None
    page = region.page or (1 if count == 1 else None)
    if page is None or page > count:
        return None
    return replace(
        region,
        page=page,
        width=min(region.width, 1 - region.left),
        height=min(region.height, 1 - region.top),
    )


def _candidates(lines: list[str], field: str, value):
    for index, line in enumerate(lines[:20_000]):
        if len(line) > 2000:
            continue
        if field == "date":
            tokens = list(_DATES.finditer(line))
            if len(tokens) == 1 and _date_from_text(tokens[0].group()) == value:
                yield 2 + _date_context_rank(line), tokens[0].group(), line
        else:
            labelled = _is_total_label_line(line)
            nearby = _BARE_MONEY.fullmatch(line) and any(
                _is_total_label_line(prev) for prev in lines[max(0, index - 3) : index]
            )
            if labelled or nearby:
                for token in _MONEY.finditer(line):
                    if _money_from_text(token.group()) == value:
                        yield 2 if labelled else 3, token.group().strip(), line


def _ocr_region(blocks: tuple[dict, ...], field: str, value, count: int):
    matches = []
    lines = [str(block.get("Text") or "") for block in blocks]
    for index, block in enumerate(blocks):
        kind = str(block.get("FieldType") or "").upper()
        known = kind in (
            ("INVOICE_RECEIPT_DATE", "DATE")
            if field == "date"
            else ("TOTAL", "AMOUNT_DUE", "GRAND_TOTAL")
        )
        parsed = (
            _date_from_text(lines[index]) if field == "date" else _money_from_text(lines[index])
        )
        if kind and not known:
            continue
        ranks = (
            [0]
            if known and parsed == value
            else [
                rank
                for rank, _token, matching_line in _candidates(
                    lines[max(0, index - 3) : index + 1], field, value
                )
                if matching_line == lines[index]
            ]
        )
        if not ranks:
            continue
        box = (block.get("Geometry") or {}).get("BoundingBox")
        if not isinstance(box, dict):
            continue
        try:
            region = _resolve_page(
                FolioRegion(
                    block.get("Page"),
                    float(box["Left"]),
                    float(box["Top"]),
                    float(box["Width"]),
                    float(box["Height"]),
                ),
                count,
            )
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
        if region is not None:
            matches.append((min(ranks), region))
    return _unique_region(matches)


def _unique_region(candidates):
    if not candidates:
        return None
    rank = min(item[0] for item in candidates)
    regions = {region for score, region in candidates if score == rank}
    return next(iter(regions)) if len(regions) == 1 else None


def _pdf_token_regions(page, text_page, token: str, line: str, number: int):
    # Locate the value only inside its labelled line, not a subtotal or another date.
    lines = _native_rectangles(text_page, line)
    if len(lines) != 1:
        return []
    left, bottom, right, top = lines[0]
    return [
        region
        for box in _native_rectangles(text_page, token)
        if left - 1 <= box[0] and bottom - 1 <= box[1] and box[2] <= right + 1 and box[3] <= top + 1
        if (region := _pdf_region(page, box, number)) is not None
    ]


def _native_rectangles(text_page, text: str):
    if not text or len(text) > 240:
        return []
    search = text_page.search(text)
    found = []
    try:
        for _ in range(32):
            match = search.get_next()
            if match is None:
                break
            boxes = [text_page.get_charbox(index) for index in range(match[0], match[0] + match[1])]
            boxes = [
                box
                for box in boxes
                if all(isfinite(v) for v in box) and box[2] > box[0] and box[3] > box[1]
            ]
            if boxes:
                found.append(
                    (
                        min(b[0] for b in boxes),
                        min(b[1] for b in boxes),
                        max(b[2] for b in boxes),
                        max(b[3] for b in boxes),
                    )
                )
    finally:
        search.close()
    return found


def _pdf_region(page, box, number: int):
    import pypdfium2.raw as pdfium_c

    width, height = page.get_size()
    device_width, device_height = max(1, round(width * 100)), max(1, round(height * 100))
    points = []
    for x in (box[0], box[2]):
        for y in (box[1], box[3]):
            dx, dy = c_int(), c_int()
            if not pdfium_c.FPDF_PageToDevice(
                page.raw, 0, 0, device_width, device_height, 0, x, y, byref(dx), byref(dy)
            ):
                return None
            points.append((dx.value / device_width, dy.value / device_height))
    left, top = min(p[0] for p in points), min(p[1] for p in points)
    right, bottom = max(p[0] for p in points), max(p[1] for p in points)
    region = FolioRegion(number, left, top, right - left, bottom - top)
    return region if region.is_valid() else None
