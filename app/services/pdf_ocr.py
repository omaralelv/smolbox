from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing
from io import BytesIO
from math import isfinite, sqrt
from threading import Lock
from uuid import UUID

from PIL import Image

from app.services.ocr_folio import FolioRegion

MAX_PDF_OCR_PAGES = 20
MAX_OCR_IMAGE_PIXELS = 8_000_000
MAX_OCR_IMAGE_SIDE = 4_000
MAX_OCR_IMAGE_BYTES = 10 * 1024 * 1024
PDF_RENDER_DPI = 200
MAX_FOLIO_PREVIEW_BYTES = 192 * 1024
INVOICE_HEADER_HEIGHT_RATIO = 0.4

# PDFium calls must be serialized, including document creation and cleanup.
_PDFIUM_LOCK = Lock()


class PdfOcrRenderError(RuntimeError):
    pass


def render_pdf_pages(content: bytes) -> Iterator[bytes]:
    """Render one page at a time in memory; leave the uploaded PDF untouched."""
    document = None
    try:
        import pypdfium2 as pdfium

        with _PDFIUM_LOCK:
            document = pdfium.PdfDocument(content)
            page_count = len(document)
        if not 1 <= page_count <= MAX_PDF_OCR_PAGES:
            raise PdfOcrRenderError(
                f"PDF OCR recovery supports 1 to {MAX_PDF_OCR_PAGES} pages; got {page_count}."
            )

        for index in range(page_count):
            with _PDFIUM_LOCK:
                image = _render_page(document, index)
            try:
                png_content = _image_as_png(image)
            finally:
                image.close()
            yield png_content
    except PdfOcrRenderError:
        raise
    except Exception as exc:
        raise PdfOcrRenderError(f"Could not render PDF for OCR: {exc}") from exc
    finally:
        if document is not None:
            with _PDFIUM_LOCK:
                document.close()


def render_invoice_header(content: bytes, *, is_pdf: bool) -> bytes:
    """Prepare one bounded, enlarged header without changing the source document."""
    if is_pdf:
        with closing(render_pdf_pages(content)) as pages:
            content = next(pages)
    try:
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > MAX_OCR_IMAGE_PIXELS:
                raise PdfOcrRenderError("Invoice image exceeds the header recovery pixel limit.")
            header_height = max(1, int(image.height * INVOICE_HEADER_HEIGHT_RATIO))
            with (
                image.crop((0, 0, image.width, header_height)) as cropped,
                cropped.convert("RGB") as header,
            ):
                scale = min(
                    2.0,
                    MAX_OCR_IMAGE_SIDE / max(header.size),
                    sqrt(MAX_OCR_IMAGE_PIXELS / (header.width * header.height)),
                )
                size = (
                    max(1, int(header.width * scale)),
                    max(1, int(header.height * scale)),
                )
                with header.resize(size, Image.Resampling.LANCZOS) as enlarged:
                    return _image_as_png(enlarged)
    except PdfOcrRenderError:
        raise
    except Exception as exc:
        raise PdfOcrRenderError(f"Could not prepare invoice header for OCR: {exc}") from exc


def _render_page_bitmap(page):
    width, height = page.get_size()
    if not all(isfinite(value) and value > 0 for value in (width, height)):
        raise PdfOcrRenderError("PDF page has invalid dimensions.")
    scale = min(
        PDF_RENDER_DPI / 72,
        (MAX_OCR_IMAGE_SIDE - 1) / max(width, height),
        sqrt((MAX_OCR_IMAGE_PIXELS - 2 * MAX_OCR_IMAGE_SIDE) / (width * height)),
    )
    return page.render(scale=scale, rev_byteorder=True)


def _render_page(document, index: int) -> Image.Image:
    page = document[index]
    try:
        bitmap = _render_page_bitmap(page)
        try:
            with bitmap.to_pil() as image:
                return image.convert("RGB")
        finally:
            bitmap.close()
    finally:
        page.close()


def render_folio_preview(
    content: bytes, *, content_type: str, folio: str, region: FolioRegion | None = None
) -> tuple[bytes, int] | None:
    """Optional, bounded crop of the actual document; never an OCR reconstruction."""
    if region is not None and not region.is_valid():
        return None
    try:
        target = UUID(folio).hex.upper()
        if content_type == "application/pdf":
            rendered = _pdf_folio_image(content, target, region)
            if rendered is None:
                return None
            image, rectangle, page_number = rendered
        elif region is not None:
            with Image.open(BytesIO(content)) as original:
                if (
                    original.width * original.height > MAX_OCR_IMAGE_PIXELS
                    or original.getexif().get(274, 1) != 1
                ):
                    return None
                image = original.convert("RGB")
            rectangle = _region_pixels(region, image)
            page_number = region.page or 1
        else:
            return None
        try:
            cropped = _folio_crop(image, rectangle)
            return (cropped, page_number) if cropped is not None else None
        finally:
            image.close()
    except Exception as exc:
        raise PdfOcrRenderError(f"Could not prepare fiscal UUID preview: {exc}") from exc


def _pdf_folio_image(content: bytes, target: str, region: FolioRegion | None):
    import pypdfium2 as pdfium

    with _PDFIUM_LOCK:
        document = pdfium.PdfDocument(content)
        try:
            count = len(document)
            if not 1 <= count <= MAX_PDF_OCR_PAGES:
                return None
            if region is not None:
                number = region.page or (1 if count == 1 else None)
                if number is None or not 1 <= number <= count:
                    return None
                image = _render_page(document, number - 1)
                return image, _region_pixels(region, image), number
            for index in range(count):
                page = document[index]
                try:
                    rectangle = _find_pdf_folio_rectangle(page, target)
                    if rectangle is None:
                        continue
                    bitmap = _render_page_bitmap(page)
                    try:
                        converter = bitmap.get_posconv(page)
                        left, bottom, right, top = rectangle
                        points = [
                            converter.to_bitmap(x, y)
                            for x in (left, right) for y in (bottom, top)
                        ]
                        bounds = (
                            min(p[0] for p in points), min(p[1] for p in points),
                            max(p[0] for p in points), max(p[1] for p in points),
                        )
                        with bitmap.to_pil() as source:
                            image = source.convert("RGB")
                        return image, bounds, index + 1
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        finally:
            document.close()
    return None


def _find_pdf_folio_rectangle(page, target: str):
    import pypdfium2.raw as pdfium_c

    text = page.get_textpage()
    try:
        search = text.search(target[:8])
        try:
            for _ in range(8):
                found = search.get_next()
                if found is None:
                    break
                indices, characters = [], []
                for index in range(found[0], min(text.count_chars(), found[0] + 160)):
                    character = chr(pdfium_c.FPDFText_GetUnicode(text, index))
                    if character.isascii() and character.isalnum():
                        characters.append(character.upper())
                        indices.append(index)
                        if len(characters) == 32:
                            break
                if "".join(characters) != target:
                    continue
                boxes = [text.get_charbox(index) for index in indices]
                if not all(
                    all(isfinite(value) for value in box)
                    and box[2] > box[0] and box[3] > box[1]
                    for box in boxes
                ):
                    continue
                bounds = (
                    min(b[0] for b in boxes), min(b[1] for b in boxes),
                    max(b[2] for b in boxes), max(b[3] for b in boxes),
                )
                width, height = page.get_size()
                if (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) <= width * height * .25:
                    return bounds
        finally:
            search.close()
    finally:
        text.close()
    return None


def _region_pixels(region: FolioRegion, image: Image.Image):
    return (
        region.left * image.width, region.top * image.height,
        (region.left + region.width) * image.width, (region.top + region.height) * image.height,
    )


def _folio_crop(image: Image.Image, rectangle) -> bytes | None:
    padding = 12
    left, top, right, bottom = rectangle
    bounds = (
        max(0, int(left) - padding), max(0, int(top) - padding),
        min(image.width, int(right) + padding + 1), min(image.height, int(bottom) + padding + 1),
    )
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        return None
    with image.crop(bounds) as cropped:
        if all(low == high for low, high in cropped.getextrema()):
            return None
        cropped.thumbnail((1400, 400), Image.Resampling.LANCZOS)
        while True:
            output = BytesIO()
            cropped.save(output, format="PNG")
            if output.tell() <= MAX_FOLIO_PREVIEW_BYTES:
                return output.getvalue()
            if min(cropped.size) <= 16:
                return None
            cropped.thumbnail(
                (max(1, cropped.width // 2), max(1, cropped.height // 2)), Image.Resampling.LANCZOS
            )


def _image_as_png(image: Image.Image) -> bytes:
    current = image
    try:
        while True:
            output = BytesIO()
            current.save(output, format="PNG")
            content = output.getvalue()
            if len(content) <= MAX_OCR_IMAGE_BYTES:
                return content
            if current.width <= 1 or current.height <= 1:
                raise PdfOcrRenderError("Rendered PDF page exceeds the OCR image size limit.")
            resized = current.resize(
                (max(1, int(current.width * 0.75)), max(1, int(current.height * 0.75))),
                Image.Resampling.LANCZOS,
            )
            if current is not image:
                current.close()
            current = resized
    finally:
        if current is not image:
            current.close()
