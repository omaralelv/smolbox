from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from math import isfinite, sqrt
from threading import Lock

from PIL import Image

MAX_PDF_OCR_PAGES = 20
MAX_OCR_IMAGE_PIXELS = 8_000_000
MAX_OCR_IMAGE_SIDE = 4_000
MAX_OCR_IMAGE_BYTES = 10 * 1024 * 1024
PDF_RENDER_DPI = 200

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


def _render_page(document, index: int) -> Image.Image:
    page = document[index]
    try:
        width, height = page.get_size()
        if not all(isfinite(value) and value > 0 for value in (width, height)):
            raise PdfOcrRenderError(f"PDF page {index + 1} has invalid dimensions.")
        # PDFium rounds bitmap dimensions up; reserve pixels for that rounding.
        scale = min(
            PDF_RENDER_DPI / 72,
            (MAX_OCR_IMAGE_SIDE - 1) / max(width, height),
            sqrt((MAX_OCR_IMAGE_PIXELS - 2 * MAX_OCR_IMAGE_SIDE) / (width * height)),
        )
        bitmap = page.render(scale=scale, rev_byteorder=True)
        try:
            with bitmap.to_pil() as image:
                return image.convert("RGB")
        finally:
            bitmap.close()
    finally:
        page.close()


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
