from app.models.ocr_extraction import OcrExtraction, OcrExtractionStatus
from app.services.textract_ocr import TextractOcrResult


def extraction_from_ocr_result(result: TextractOcrResult, **metadata) -> OcrExtraction:
    return OcrExtraction(
        status=OcrExtractionStatus.succeeded,
        raw_text=result.raw_text,
        extracted_total=result.extracted_total,
        extracted_date=result.extracted_date,
        extracted_supplier=result.extracted_supplier,
        suggested_cfdi_uuid=result.suggested_cfdi_uuid,
        confidence=result.confidence,
        raw_response=result.raw_response,
        **metadata,
    )


def ocr_result_from_extraction(extraction: OcrExtraction) -> TextractOcrResult:
    return TextractOcrResult(
        raw_text=extraction.raw_text or "",
        extracted_total=extraction.extracted_total,
        extracted_date=extraction.extracted_date,
        extracted_supplier=extraction.extracted_supplier,
        suggested_cfdi_uuid=extraction.suggested_cfdi_uuid,
        confidence=extraction.confidence,
        raw_response=extraction.raw_response,
    )
