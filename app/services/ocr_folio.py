"""Locate the selected fiscal UUID without changing OCR text or fiscal validation."""

import re
from dataclasses import dataclass
from math import isfinite
from uuid import UUID


@dataclass(frozen=True)
class FolioRegion:
    page: int | None
    left: float
    top: float
    width: float
    height: float

    def is_valid(self) -> bool:
        values = (self.left, self.top, self.width, self.height)
        return (
            all(isinstance(value, (int, float)) and isfinite(value) for value in values)
            and (self.page is None or type(self.page) is int and 1 <= self.page <= 20)
            and 0 <= self.left < 1
            and 0 <= self.top < 1
            and 0 < self.width <= 1
            and 0 < self.height <= 1
            and self.width * self.height <= 0.25
            and self.left + self.width <= 1.001
            and self.top + self.height <= 1.001
        )


def compact_folio_text(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def locate_folio_region(
    blocks: list[dict], folio: str | None, *, page_number: int | None = None
) -> FolioRegion | None:
    if not folio:
        return None
    try:
        target = UUID(folio).hex.upper()
    except (ValueError, AttributeError):
        return None
    groups: dict[str, list[tuple[str, FolioRegion]]] = {"LINE": [], "WORD": []}
    for block in blocks[:20_000]:
        if not isinstance(block, dict) or block.get("BlockType") not in groups:
            continue
        geometry = block.get("Geometry")
        box = geometry.get("BoundingBox") if isinstance(geometry, dict) else None
        if not isinstance(box, dict) or not isinstance(block.get("Text"), str):
            continue
        try:
            region = FolioRegion(
                page_number if page_number is not None else block.get("Page"),
                float(box["Left"]),
                float(box["Top"]),
                float(box["Width"]),
                float(box["Height"]),
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not region.is_valid():
            continue
        text = compact_folio_text(block["Text"][:2000])
        if target in text:
            return region
        groups[block["BlockType"]].append((text, region))

    for kind, entries in groups.items():
        limit = 4 if kind == "LINE" else 6
        for index, (text, region) in enumerate(entries):
            selected = region
            for other_text, other in entries[index + 1 : index + limit]:
                if other.page != selected.page:
                    break
                gap = max(
                    other.top - selected.top - selected.height,
                    selected.top - other.top - other.height,
                )
                if gap > 0.04:
                    break
                left, top = min(selected.left, other.left), min(selected.top, other.top)
                right = max(selected.left + selected.width, other.left + other.width)
                bottom = max(selected.top + selected.height, other.top + other.height)
                selected = FolioRegion(region.page, left, top, right - left, bottom - top)
                if not selected.is_valid():
                    break
                text += other_text
                if target in text:
                    return selected
    return None
