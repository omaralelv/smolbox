from app.services.textract_ocr import _parse_analyze_expense_response


def test_analyze_expense_suggests_cfdi_uuid_from_ocr_text() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {
                            "BlockType": "LINE",
                            "Text": "Folio Fiscal 11111111-2222-3333-4444-aaaaaaaaaaaa",
                        }
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.suggested_cfdi_uuid == "11111111-2222-3333-4444-AAAAAAAAAAAA"


def test_analyze_expense_suggests_cfdi_uuid_from_compact_ocr_text() -> None:
    result = _parse_analyze_expense_response(
        {
            "ExpenseDocuments": [
                {
                    "Blocks": [
                        {
                            "BlockType": "LINE",
                            "Text": "UUID 11111111222233334444aaaaaaaaaaaa",
                        }
                    ],
                    "SummaryFields": [],
                }
            ]
        },
        store_raw_response=False,
    )

    assert result.suggested_cfdi_uuid == "11111111-2222-3333-4444-AAAAAAAAAAAA"
