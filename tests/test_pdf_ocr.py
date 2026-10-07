from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfWriter

from app.services import pdf_ocr
from app.services.pdf_ocr import PdfOcrRenderError, render_pdf_pages


def _blank_pdf(page_count: int, *, width: int = 612, height: int = 792, password=None) -> bytes:
    output = BytesIO()
    with PdfWriter() as writer:
        for _ in range(page_count):
            writer.add_blank_page(width=width, height=height)
        if password is not None:
            writer.encrypt(password)
        writer.write(output)
    return output.getvalue()


def test_pdf_renderer_returns_a_png_for_every_page() -> None:
    pages = list(render_pdf_pages(_blank_pdf(2)))
    assert len(pages) == 2
    for content in pages:
        with Image.open(BytesIO(content)) as image:
            assert image.format == "PNG"
            assert image.mode == "RGB"
            assert image.width > 1000
            assert image.height > 1000


@pytest.mark.parametrize(("width", "height"), [(20000, 10000), (12345, 9876)])
def test_pdf_renderer_bounds_large_page_dimensions(width, height) -> None:
    content = next(render_pdf_pages(_blank_pdf(1, width=width, height=height)))
    with Image.open(BytesIO(content)) as image:
        assert max(image.size) <= pdf_ocr.MAX_OCR_IMAGE_SIDE
        assert image.width * image.height <= pdf_ocr.MAX_OCR_IMAGE_PIXELS
    assert len(content) <= pdf_ocr.MAX_OCR_IMAGE_BYTES


def test_pdf_renderer_rejects_excessive_page_count_before_processing_pages() -> None:
    with pytest.raises(PdfOcrRenderError, match="pages"):
        list(render_pdf_pages(_blank_pdf(pdf_ocr.MAX_PDF_OCR_PAGES + 1)))


def test_pdf_renderer_does_not_unlock_password_protected_documents() -> None:
    with pytest.raises(PdfOcrRenderError):
        list(render_pdf_pages(_blank_pdf(1, password="test-password")))


def test_pdf_renderer_rejects_a_corrupted_pdf() -> None:
    with pytest.raises(PdfOcrRenderError):
        list(render_pdf_pages(b"%PDF-1.4\ncorrupted\n%%EOF"))


def test_png_encoding_limits_file_size_without_modifying_the_source_image(monkeypatch) -> None:
    monkeypatch.setattr(pdf_ocr, "MAX_OCR_IMAGE_BYTES", 1024)
    with Image.effect_noise((512, 512), 80) as image:
        content = pdf_ocr._image_as_png(image)
        assert image.size == (512, 512)
    assert len(content) <= 1024
    with Image.open(BytesIO(content)) as image:
        assert image.format == "PNG"
        assert image.width < 512
