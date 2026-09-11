from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient


def _xlsx_bytes(rows: list[list[str]]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w") as workbook:
        workbook.writestr("[Content_Types].xml", "<Types />")
        workbook.writestr(
            "xl/workbook.xml",
            (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
            ),
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/></Relationships>'
            ),
        )
        workbook.writestr("xl/worksheets/sheet1.xml", _sheet_xml(rows))
    return output.getvalue()


def _sheet_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            column = chr(ord("A") + column_number - 1)
            cells.append(
                f'<c r="{column}{row_number}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        row_xml.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )


def test_imports_expenses_from_csv(client: TestClient, base_records: dict[str, str]) -> None:
    csv_content = (
        b"proveedor,importe,fecha,categoria,descripcion,rfc_proveedor\n"
        b"Papeleria Uno,1000.00,2026-08-10,Papeleria,Hojas y plumas,XAXX010101000\n"
        b"Taxi Demo,500.00,2026-08-11,Transporte,Traslado local,XEXX010101000\n"
    )

    imported = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/expenses/import",
        data={"dry_run": "false"},
        files={"file": ("gastos.csv", csv_content, "text/csv")},
    )

    assert imported.status_code == 201, imported.text
    body = imported.json()
    assert body["imported_count"] == 2
    assert body["dry_run"] is False
    assert body["attachment_id"] is not None
    assert [expense["merchant"] for expense in body["expenses"]] == [
        "Papeleria Uno",
        "Taxi Demo",
    ]

    summary = client.get(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/validation-summary"
    )
    assert summary.status_code == 200
    assert summary.json()["expense_count"] == 2
    assert summary.json()["calculated_total"] == "1500.00"

    audit = client.get(f"/api/v1/reimbursement-requests/{base_records['request_id']}/audit-events")
    assert audit.status_code == 200
    assert "expenses_imported" in {event["action"] for event in audit.json()}


def test_previews_expenses_from_xlsx_without_saving(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    workbook = _xlsx_bytes(
        [
            ["proveedor", "importe", "fecha", "categoria"],
            ["Gasolinera Demo", "250.00", "2026-08-12", "Transporte"],
        ]
    )

    preview = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/expenses/import",
        data={"dry_run": "true"},
        files={
            "file": (
                "gastos.xlsx",
                workbook,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert preview.status_code == 201, preview.text
    assert preview.json()["imported_count"] == 1
    assert preview.json()["dry_run"] is True
    assert preview.json()["attachment_id"] is None
    assert preview.json()["expenses"] == []

    expenses = client.get(
        f"/api/v1/expenses?reimbursement_request_id={base_records['request_id']}"
    )
    assert expenses.status_code == 200
    assert expenses.json() == []


def test_rejects_import_with_invalid_rows_without_partial_writes(
    client: TestClient,
    base_records: dict[str, str],
) -> None:
    csv_content = (
        b"proveedor,importe,fecha,categoria\n"
        b"Valido,100.00,2026-08-10,Papeleria\n"
        b"Fuera periodo,50.00,2026-09-30,Transporte\n"
    )

    imported = client.post(
        f"/api/v1/reimbursement-requests/{base_records['request_id']}/expenses/import",
        data={"dry_run": "false"},
        files={"file": ("gastos.csv", csv_content, "text/csv")},
    )

    assert imported.status_code == 422
    assert imported.json()["detail"]["code"] == "IMPORT_VALIDATION_FAILED"
    assert imported.json()["detail"]["errors"][0]["field"] == "spent_on"

    expenses = client.get(
        f"/api/v1/expenses?reimbursement_request_id={base_records['request_id']}"
    )
    assert expenses.status_code == 200
    assert expenses.json() == []
