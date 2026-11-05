from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing
from io import BytesIO
from math import isfinite, sqrt
from threading import Lock

from PIL import Image

MAX_PDF_OCR_PAGES = 20
MAX_OCR_IMAGE_PIXELS = 8_000_000
MAX_OCR_IMAGE_SIDE = 4_000
MAX_OCR_IMAGE_BYTES = 10 * 1024 * 1024
PDF_RENDER_DPI = 200
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


def find_pdf_folio_rectangle(page, target: str):
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
                    all(isfinite(value) for value in box) and box[2] > box[0] and box[3] > box[1]
                    for box in boxes
                ):
                    continue
                bounds = (
                    min(b[0] for b in boxes),
                    min(b[1] for b in boxes),
                    max(b[2] for b in boxes),
                    max(b[3] for b in boxes),
                )
                width, height = page.get_size()
                if (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) <= width * height * 0.25:
                    return bounds
        finally:
            search.close()
    finally:
        text.close()
    return None


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
