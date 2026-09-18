from datetime import date

from openpyxl import Workbook

from app.api.v1.endpoints.macro_sap import (
    _formatear_fecha_ultimo_gasto,
    _resaltar_uidd_necesario,
)


def test_formatear_fecha_ultimo_gasto_usa_la_fecha_mas_reciente() -> None:
    gastos = [
        {"spent_on": date(2026, 8, 10)},
        {"spent_on": date(2026, 8, 30)},
        {"spent_on": date(2026, 8, 18)},
    ]

    assert _formatear_fecha_ultimo_gasto(gastos) == "30/08/2026"


def test_resaltar_uidd_necesario_aplica_amarillo_en_columna_h() -> None:
    worksheet = Workbook().active
    worksheet.append(["S", "cuenta", 100, "V1", "T001", "", "CAJA CHICA", "DATO NECESARIO"])

    _resaltar_uidd_necesario(worksheet, worksheet.max_row, "DATO NECESARIO")

    assert worksheet["H1"].fill.fill_type == "solid"
    assert worksheet["H1"].fill.fgColor.rgb == "00FFFF00"
    assert worksheet["G1"].fill.fill_type is None


def test_resaltar_uidd_necesario_no_modifica_otro_uidd() -> None:
    worksheet = Workbook().active
    worksheet.append(["S", "cuenta", 100, "V1", "T001", "", "CAJA CHICA", "CFDI-123"])

    _resaltar_uidd_necesario(worksheet, worksheet.max_row, "CFDI-123")

    assert worksheet["H1"].fill.fill_type is None
