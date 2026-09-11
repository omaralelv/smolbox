from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile


class ExpenseImportUnsupported(ValueError):
    pass


@dataclass(frozen=True)
class ExpenseImportRow:
    row_number: int
    merchant: str
    amount: Decimal
    currency: str
    spent_on: date
    category: str | None = None
    description: str | None = None
    supplier_tax_id: str | None = None
    requires_authorization: bool = False


@dataclass(frozen=True)
class ExpenseImportRowError:
    row_number: int
    field: str
    message: str


COLUMN_ALIASES = {
    "merchant": "merchant",
    "proveedor": "merchant",
    "comercio": "merchant",
    "establecimiento": "merchant",
    "concepto": "description",
    "amount": "amount",
    "importe": "amount",
    "monto": "amount",
    "total": "amount",
    "spent_on": "spent_on",
    "fecha": "spent_on",
    "fecha_gasto": "spent_on",
    "fecha_de_gasto": "spent_on",
    "fecha_compra": "spent_on",
    "currency": "currency",
    "moneda": "currency",
    "category": "category",
    "categoria": "category",
    "rubro": "category",
    "description": "description",
    "descripcion": "description",
    "detalle": "description",
    "supplier_tax_id": "supplier_tax_id",
    "supplier_rfc": "supplier_tax_id",
    "rfc": "supplier_tax_id",
    "rfc_proveedor": "supplier_tax_id",
    "rfc_emisor": "supplier_tax_id",
    "requires_authorization": "requires_authorization",
    "requiere_autorizacion": "requires_authorization",
    "requiere_autorización": "requires_authorization",
    "autorizacion": "requires_authorization",
    "autorización": "requires_authorization",
}

REQUIRED_COLUMNS = {"merchant", "amount", "spent_on"}


def parse_expense_import(
    content: bytes,
    filename: str,
) -> tuple[list[ExpenseImportRow], list[ExpenseImportRowError]]:
    extension = Path(filename).suffix.lower()
    if extension == ".csv":
        table = _read_csv(content)
    elif extension == ".xlsx":
        table = _read_xlsx(content)
    elif extension == ".xls":
        raise ExpenseImportUnsupported(
            "XLS binary files cannot be imported yet; save the file as XLSX or CSV."
        )
    else:
        raise ExpenseImportUnsupported("Expense import files must be CSV or XLSX.")

    return _rows_from_table(table)


def _rows_from_table(
    table: list[list[object]],
) -> tuple[list[ExpenseImportRow], list[ExpenseImportRowError]]:
    header_index = _find_header_index(table)
    if header_index is None:
        return [], [ExpenseImportRowError(row_number=1, field="file", message="No header row found")]

    headers = [_canonical_column_name(cell) for cell in table[header_index]]
    header_map = {index: header for index, header in enumerate(headers) if header}
    present_columns = set(header_map.values())
    missing_columns = REQUIRED_COLUMNS - present_columns
    if missing_columns:
        errors = [
            ExpenseImportRowError(
                row_number=header_index + 1,
                field=column,
                message="Required column is missing",
            )
            for column in sorted(missing_columns)
        ]
        return [], errors

    imported_rows: list[ExpenseImportRow] = []
    errors: list[ExpenseImportRowError] = []

    for row_index, raw_row in enumerate(table[header_index + 1 :], start=header_index + 2):
        if not _has_any_value(raw_row):
            continue

        values: dict[str, object] = {}
        for column_index, field_name in header_map.items():
            values[field_name] = raw_row[column_index] if column_index < len(raw_row) else ""

        row, row_errors = _parse_row(row_index, values)
        if row_errors:
            errors.extend(row_errors)
        elif row is not None:
            imported_rows.append(row)

    return imported_rows, errors


def _parse_row(
    row_number: int,
    values: dict[str, object],
) -> tuple[ExpenseImportRow | None, list[ExpenseImportRowError]]:
    errors: list[ExpenseImportRowError] = []

    merchant = _clean_string(values.get("merchant"))
    if merchant is None:
        errors.append(_row_error(row_number, "merchant", "Merchant is required"))

    amount = _parse_amount(values.get("amount"))
    if amount is None or amount <= Decimal("0.00"):
        errors.append(_row_error(row_number, "amount", "Amount must be a positive number"))

    spent_on = _parse_date(values.get("spent_on"))
    if spent_on is None:
        errors.append(
            _row_error(
                row_number,
                "spent_on",
                "Date must use YYYY-MM-DD, DD/MM/YYYY, or an Excel date cell",
            )
        )

    currency = (_clean_string(values.get("currency")) or "MXN").upper()
    if len(currency) != 3:
        errors.append(_row_error(row_number, "currency", "Currency must have 3 letters"))

    if errors:
        return None, errors

    assert merchant is not None
    assert amount is not None
    assert spent_on is not None

    return (
        ExpenseImportRow(
            row_number=row_number,
            merchant=merchant,
            amount=amount,
            currency=currency,
            spent_on=spent_on,
            category=_clean_string(values.get("category")),
            description=_clean_string(values.get("description")),
            supplier_tax_id=_clean_string(values.get("supplier_tax_id"), uppercase=True),
            requires_authorization=_parse_bool(values.get("requires_authorization")),
        ),
        [],
    )


def _read_csv(content: bytes) -> list[list[object]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExpenseImportUnsupported("CSV imports must be UTF-8 text.") from exc

    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    return [list(row) for row in csv.reader(StringIO(text), dialect)]


def _read_xlsx(content: bytes) -> list[list[object]]:
    try:
        with ZipFile(BytesIO(content)) as workbook:
            names = set(workbook.namelist())
            sheet_path = _first_sheet_path(workbook, names)
            shared_strings = _shared_strings(workbook, names)
            sheet_xml = workbook.read(sheet_path)
    except BadZipFile as exc:
        raise ExpenseImportUnsupported("The XLSX file is not a valid Office workbook.") from exc
    except KeyError as exc:
        raise ExpenseImportUnsupported("The XLSX file does not contain a readable sheet.") from exc

    root = ElementTree.fromstring(sheet_xml)
    rows: list[list[object]] = []
    for row_element in _iter_local(root, "row"):
        row_values: list[object] = []
        for cell in _iter_local(row_element, "c"):
            cell_ref = cell.attrib.get("r", "")
            column_index = _column_index(cell_ref)
            while len(row_values) <= column_index:
                row_values.append("")
            row_values[column_index] = _xlsx_cell_value(cell, shared_strings)
        rows.append(row_values)
    return rows


def _first_sheet_path(workbook: ZipFile, names: set[str]) -> str:
    if "xl/workbook.xml" not in names:
        raise KeyError("xl/workbook.xml")

    workbook_root = ElementTree.fromstring(workbook.read("xl/workbook.xml"))
    sheet = next(_iter_local(workbook_root, "sheet"), None)
    if sheet is None:
        raise KeyError("sheet")

    relationship_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    if not relationship_id:
        return "xl/worksheets/sheet1.xml"

    rels_root = ElementTree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    for rel in _iter_local(rels_root, "Relationship"):
        if rel.attrib.get("Id") == relationship_id:
            target = rel.attrib.get("Target", "")
            if target.startswith("/"):
                return target.lstrip("/")
            return f"xl/{target}".replace("xl/../", "")

    raise KeyError(relationship_id)


def _shared_strings(workbook: ZipFile, names: set[str]) -> list[str]:
    if "xl/sharedStrings.xml" not in names:
        return []

    root = ElementTree.fromstring(workbook.read("xl/sharedStrings.xml"))
    return ["".join(text.text or "" for text in _iter_local(item, "t")) for item in _iter_local(root, "si")]


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> object:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in _iter_local(cell, "t"))

    value_element = next(_iter_local(cell, "v"), None)
    raw_value = "" if value_element is None else value_element.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (IndexError, ValueError):
            return raw_value
    return raw_value


def _canonical_column_name(value: object) -> str | None:
    normalized = _normalize_text(_clean_string(value) or "")
    return COLUMN_ALIASES.get(normalized)


def _normalize_text(value: str) -> str:
    without_accents = "".join(
        char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "_", without_accents.lower()).strip("_")


def _find_header_index(table: list[list[object]]) -> int | None:
    for index, row in enumerate(table):
        canonical_headers = {_canonical_column_name(cell) for cell in row}
        if REQUIRED_COLUMNS.issubset(canonical_headers):
            return index
    return None


def _has_any_value(row: list[object]) -> bool:
    return any(_clean_string(value) is not None for value in row)


def _clean_string(value: object, *, uppercase: bool = False) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return cleaned.upper() if uppercase else cleaned


def _parse_bool(value: object) -> bool:
    cleaned = _clean_string(value)
    if cleaned is None:
        return False
    return cleaned.strip().lower() in {"1", "true", "t", "yes", "y", "si", "sí", "x"}


def _parse_amount(value: object) -> Decimal | None:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None
    normalized = cleaned.replace("$", "").replace(" ", "")
    if "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    try:
        return Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _parse_date(value: object) -> date | None:
    cleaned = _clean_string(value)
    if cleaned is None:
        return None

    if re.fullmatch(r"\d+(\.\d+)?", cleaned):
        return _excel_serial_date(cleaned)

    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        pass

    slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", cleaned)
    if slash_match is None:
        return None

    first, second, year = (int(part) for part in slash_match.groups())
    for day, month in ((first, second), (second, first)):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    return None


def _excel_serial_date(value: str) -> date | None:
    try:
        serial = float(value)
    except ValueError:
        return None
    if serial <= 0:
        return None
    return date(1899, 12, 30) + timedelta(days=int(serial))


def _column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Za-z]", "", cell_ref).upper()
    if not letters:
        return 0
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _iter_local(element: ElementTree.Element, local_name: str):
    return (
        child
        for child in element.iter()
        if child.tag.rsplit("}", maxsplit=1)[-1] == local_name
    )


def _row_error(row_number: int, field: str, message: str) -> ExpenseImportRowError:
    return ExpenseImportRowError(row_number=row_number, field=field, message=message)
