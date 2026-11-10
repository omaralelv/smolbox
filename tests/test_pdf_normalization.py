import builtins
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services import pdf_normalization
from app.services.pdf_normalization import PdfNormalizationError, normalize_pdf_for_processing

MAX_BYTES = 1024 * 1024
PREFIX = b"^{doc_title = invoice-test}\r\n"


def _pdf(page_count=1, *, password=None, width=612, height=792) -> bytes:
    with PdfWriter() as writer, BytesIO() as output:
        writer.pdf_header = "%PDF-1.6"
        writer.add_metadata({"/Title": "Normalization test"})
        for _ in range(page_count):
            page = writer.add_blank_page(width=width, height=height)
            page.rotate(90)
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
                }
            )
            stream = DecodedStreamObject()
            stream.set_data(b"BT /F1 12 Tf 20 30 Td (Total 100.00) Tj ET")
            page[NameObject("/Contents")] = writer._add_object(stream)
        if password is not None:
            writer.encrypt(password)
        writer.write(output)
        return output.getvalue()


def test_normalization_preserves_pdf_version_text_pages_metadata_and_content(caplog) -> None:
    original = PREFIX + _pdf(2)
    source = PdfReader(BytesIO(original))
    with caplog.at_level("INFO", logger="app.services.pdf_normalization"):
        normalized = normalize_pdf_for_processing(original, max_bytes=MAX_BYTES)

    assert original.startswith(PREFIX)
    assert normalized.startswith(b"%PDF-1.6")
    assert b"%%EOF" in normalized[-2048:]
    recovered = PdfReader(BytesIO(normalized), strict=True)
    assert len(recovered.pages) == len(source.pages) == 2
    assert dict(recovered.metadata) == dict(source.metadata)
    for before, after in zip(source.pages, recovered.pages, strict=True):
        assert before.extract_text() == after.extract_text() == "Total 100.00"
        assert before.mediabox == after.mediabox
        assert before.rotation == after.rotation
        assert before.get_contents().get_data() == after.get_contents().get_data()
    assert "PDF normalized for processing" in caplog.text


@pytest.mark.parametrize("content", [b"", b"not a pdf", PREFIX + b"%PDF-1.4\nbad\n%%EOF"])
def test_normalization_rejects_fake_or_corrupt_documents(content) -> None:
    with pytest.raises(PdfNormalizationError):
        normalize_pdf_for_processing(content, max_bytes=MAX_BYTES)


def test_normalization_does_not_search_for_a_pdf_arbitrarily_far_into_a_file() -> None:
    content = b"x" * pdf_normalization.MAX_PDF_HEADER_OFFSET + _pdf()
    with pytest.raises(PdfNormalizationError, match="header"):
        normalize_pdf_for_processing(content, max_bytes=MAX_BYTES)


@pytest.mark.parametrize("page_count", [0, pdf_normalization.MAX_PDF_OCR_PAGES + 1])
def test_normalization_bounds_recovered_page_count(page_count) -> None:
    with pytest.raises(PdfNormalizationError, match="page count"):
        normalize_pdf_for_processing(PREFIX + _pdf(page_count), max_bytes=MAX_BYTES)


def test_normalization_does_not_unlock_encrypted_documents() -> None:
    with pytest.raises(PdfNormalizationError, match="Encrypted"):
        normalize_pdf_for_processing(PREFIX + _pdf(password="secret"), max_bytes=MAX_BYTES)


def test_normalization_rejects_invalid_page_dimensions() -> None:
    with pytest.raises(PdfNormalizationError, match="invalid page"):
        normalize_pdf_for_processing(PREFIX + _pdf(width=0), max_bytes=MAX_BYTES)


def test_normalization_bounds_input_size() -> None:
    original = PREFIX + _pdf()
    with pytest.raises(PdfNormalizationError, match="size limit"):
        normalize_pdf_for_processing(original, max_bytes=len(original) - 1)


def test_normalization_bounds_output_size(monkeypatch) -> None:
    original = PREFIX + _pdf()
    real_write = PdfWriter.write

    def oversized_write(self, output):
        real_write(self, output)
        output.write(b"x" * MAX_BYTES)

    monkeypatch.setattr(PdfWriter, "write", oversized_write)
    with pytest.raises(PdfNormalizationError, match="size limit"):
        normalize_pdf_for_processing(original, max_bytes=MAX_BYTES)


def test_normalization_reopens_the_generated_copy(monkeypatch) -> None:
    original = PREFIX + _pdf()
    monkeypatch.setattr(PdfWriter, "write", lambda self, output: output.write(b"broken"))
    with pytest.raises(PdfNormalizationError):
        normalize_pdf_for_processing(original, max_bytes=MAX_BYTES)


def test_normalization_reports_an_unavailable_library_without_changing_the_alert(
    monkeypatch,
) -> None:
    original = PREFIX + _pdf()
    real_import = builtins.__import__

    def missing_pypdf(name, *args, **kwargs):
        if name == "pypdf":
            raise ImportError("pypdf is not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_pypdf)
    with pytest.raises(PdfNormalizationError) as error:
        normalize_pdf_for_processing(original, max_bytes=MAX_BYTES)
    assert isinstance(error.value.__cause__, ImportError)
