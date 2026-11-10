from __future__ import annotations

import logging
import re
from io import BytesIO
from math import isfinite
from typing import TYPE_CHECKING

from app.services.pdf_ocr import MAX_PDF_OCR_PAGES

if TYPE_CHECKING:
    from pypdf import PdfReader

logger = logging.getLogger(__name__)
PDF_HEADER = re.compile(rb"%PDF-(?:1\.[0-7]|2\.0)(?=[\r\n\s])")
MAX_PDF_HEADER_OFFSET = 1024


class PdfNormalizationError(ValueError):
    pass


class _LimitedPdfBuffer(BytesIO):
    def __init__(self, max_bytes: int) -> None:
        super().__init__()
        self.max_bytes = max_bytes

    def write(self, content: bytes) -> int:
        if self.tell() + len(content) > self.max_bytes:
            raise PdfNormalizationError("Recovered PDF exceeds the upload size limit")
        return super().write(content)


def _check_pages(reader: PdfReader) -> int:
    if reader.is_encrypted:
        raise PdfNormalizationError("Encrypted PDFs cannot be normalized")
    if reader.root_object.get("/Type") != "/Catalog":
        raise PdfNormalizationError("PDF does not contain a document catalog")
    page_count = len(reader.pages)
    if not 1 <= page_count <= MAX_PDF_OCR_PAGES:
        raise PdfNormalizationError("PDF exceeds the supported recovery page count")
    for page in reader.pages:
        dimensions = (page.mediabox.width, page.mediabox.height)
        if page.get("/Type") != "/Page" or not all(
            isfinite(value) and value > 0 for value in dimensions
        ):
            raise PdfNormalizationError("PDF contains an invalid page")
    return page_count


def normalize_pdf_for_processing(content: bytes, *, max_bytes: int) -> bytes:
    """Recover a processing copy without altering the uploaded evidence."""
    if not content or len(content) > max_bytes:
        raise PdfNormalizationError("PDF exceeds the upload size limit")
    header = PDF_HEADER.search(content[:MAX_PDF_HEADER_OFFSET])
    if header is None:
        raise PdfNormalizationError("PDF header was not found near the start of the file")

    try:
        from pypdf import PdfReader, PdfWriter

        with BytesIO(content) as source:
            reader = PdfReader(source, strict=False)
            page_count = _check_pages(reader)
            with PdfWriter() as writer, _LimitedPdfBuffer(max_bytes) as output:
                writer.clone_document_from_reader(reader)
                writer.pdf_header = header.group().decode("ascii")
                writer.write(output)
                normalized = output.getvalue()

        with BytesIO(normalized) as source:
            if _check_pages(PdfReader(source, strict=True)) != page_count:
                raise PdfNormalizationError("Recovered PDF has a different page count")
    except PdfNormalizationError:
        raise
    except Exception as exc:
        logger.warning("PDF recovery failed: %s", exc)
        raise PdfNormalizationError("PDF could not be recovered") from exc

    logger.info(
        "PDF normalized for processing: original_bytes=%s normalized_bytes=%s pages=%s",
        len(content),
        len(normalized),
        page_count,
    )
    return normalized
