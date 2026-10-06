import asyncio
import io
import uuid
import zipfile
from datetime import UTC, date, datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from openpyxl import Workbook, load_workbook

from app.api.v1.endpoints import macro_sap
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


def test_generar_polizas_conserva_lineas_separadas_con_misma_cuenta(tmp_path) -> None:
    solicitud_id = uuid.uuid4()
    solicitud = {
        "store_id": "store-1",
        "period_id": "period-1",
        "reimbursement_starts_on": date(2026, 8, 5),
        "reimbursement_ends_on": date(2026, 9, 1),
        "previous_reimbursement_request_id": uuid.uuid4(),
        "previous_reimbursement_starts_on": date(2026, 7, 15),
        "previous_reimbursement_ends_on": date(2026, 7, 31),
        "previous_reimbursement_amount": "0",
        "created_at": datetime(2026, 9, 1, tzinfo=UTC),
        "folio": "TEST-1",
    }
    tienda = {"code": "V101"}
    periodo = {}
    gastos = [
        {
            "id": "expense-insumos",
            "category": "Insumos",
            "cfdi_uuid": "UUID-INSUMOS",
            "amount": "116",
            "cfdi_tax_rate": "16",
            "cfdi_tax_amount": "16",
            "cfdi_subtotal": "100",
            "effective_cfdi_uuid": "UUID-INSUMOS",
            "spent_on": date(2026, 8, 10),
        },
        {
            "id": "expense-papeleria",
            "category": "Papelería",
            "cfdi_uuid": "UUID-PAPELERIA",
            "amount": "232",
            "cfdi_tax_rate": "16",
            "cfdi_tax_amount": "32",
            "cfdi_subtotal": "200",
            "effective_cfdi_uuid": "UUID-PAPELERIA",
            "spent_on": date(2026, 8, 11),
        },
        {
            "id": "expense-manual-w6",
            "category": "Insumos",
            "cfdi_uuid": "UUID-MANUAL-W6",
            "amount": "108",
            "cfdi_tax_rate": "8",
            "cfdi_tax_amount": "8",
            "cfdi_subtotal": "100",
            "sap_tax_index_override": "W6",
            "effective_cfdi_uuid": "UUID-MANUAL-W6",
            "spent_on": date(2026, 8, 12),
        },
    ]

    resultados = []
    for valor in (solicitud, tienda, periodo, gastos):
        resultado = Mock()
        resultado.mappings.return_value.first.return_value = valor
        resultado.mappings.return_value.all.return_value = valor
        resultados.append(resultado)
    db = Mock()
    db.execute.side_effect = resultados
    db.scalar.return_value = date(2026, 7, 31)
    db.get.return_value = Mock(
        previous_reimbursement_request_id=None,
        previous_reimbursement_ends_on=date(2026, 6, 30),
    )

    plantilla = tmp_path / "plantilla.xlsx"
    Workbook().save(plantilla)

    with (
        patch.object(
            macro_sap,
            "diccionario_tiendas",
            {
                "V101": {
                    "PLAZA": "Tienda de prueba",
                    "NOMBRE_GERENTE": "Gerente",
                    "CUENTA": "Cuenta",
                    "CAJA_CHICA": "Fondo",
                    "RESPONSABLE": "Responsable",
                    "SUPERVISOR": "Supervisor",
                }
            },
        ),
        patch.object(
            macro_sap,
            "indice_categorias",
            {
                "insumos": {"codigo": "601007", "descripcion": "Insumos"},
                "papelería": {"codigo": "601007", "descripcion": "Papelería"},
            },
        ),
        patch.object(macro_sap, "tiendas_iva_w6", set()),
        patch.object(macro_sap, "ruta_plantilla", str(plantilla)),
        patch.object(macro_sap, "ruta_logo", str(tmp_path / "no-logo.png")),
        patch.object(
            macro_sap,
            "obtener_resumen_gasto_tienda",
            return_value={"current_accumulated": 0},
        ),
    ):
        response = macro_sap.generar_polizas(
            solicitud_id,
            db=db,
            current_user=Mock(id=uuid.uuid4()),
        )

        solicitud["previous_reimbursement_ends_on"] = date(2026, 8, 31)
        gastos_limite = [
            {
                "id": "expense-on-previous-end",
                "category": "Insumos",
                "cfdi_uuid": "UUID-BOUNDARY",
                "amount": "116",
                "cfdi_tax_rate": "16",
                "cfdi_tax_amount": "16",
                "cfdi_subtotal": "100",
                "effective_cfdi_uuid": "UUID-BOUNDARY",
                "spent_on": date(2026, 8, 31),
            }
        ]
        resultados_limite = []
        for valor in (solicitud, tienda, periodo, gastos_limite):
            resultado = Mock()
            resultado.mappings.return_value.first.return_value = valor
            resultado.mappings.return_value.all.return_value = valor
            resultados_limite.append(resultado)
        db.execute.side_effect = resultados_limite
        db.scalar.return_value = date(2026, 8, 31)
        response_limite = macro_sap.generar_polizas(
            solicitud_id,
            db=db,
            current_user=Mock(id=uuid.uuid4()),
        )

    async def leer_respuesta(respuesta) -> bytes:
        return b"".join([parte async for parte in respuesta.body_iterator])

    contenido_zip = asyncio.run(leer_respuesta(response))
    with zipfile.ZipFile(io.BytesIO(contenido_zip)) as archivo_zip:
        contenido_poliza = archivo_zip.read("Poliza Reembolso TEST-1.xlsx")
        contenido_sap = archivo_zip.read("CAJA CHICA TEST-1.xlsx")

    poliza = load_workbook(io.BytesIO(contenido_poliza), data_only=True).active
    filas = {
        (poliza[f"C{fila}"].value, poliza[f"D{fila}"].value)
        for fila in range(41, poliza.max_row + 1)
        if poliza[f"C{fila}"].value is not None
    }

    assert ("601007", "Insumos") in filas
    assert ("601007", "Papelería") in filas
    assert poliza["F29"].value == "01/08/2026"
    assert poliza["I29"].value == "12/08/2026"
    assert poliza["F31"].value == "01/07/2026"

    sap = load_workbook(io.BytesIO(contenido_sap), data_only=True).active
    assert sap["G1"].value == "V101 01/08/2026 AL 12/08/2026 Gerente"
    assert sap[f"H{sap.max_row}"].value == sap["G1"].value
    assert any(
        sap[f"C{fila}"].value == 108
        and sap[f"D{fila}"].value == "W6"
        for fila in range(2, sap.max_row + 1)
    )

    contenido_limite = asyncio.run(leer_respuesta(response_limite))
    with zipfile.ZipFile(io.BytesIO(contenido_limite)) as archivo_zip:
        contenido_solicitud_limite = archivo_zip.read(
            "Poliza Reembolso TEST-1.xlsx"
        )
        contenido_sap_limite = archivo_zip.read("CAJA CHICA TEST-1.xlsx")

    solicitud_limite = load_workbook(
        io.BytesIO(contenido_solicitud_limite),
        data_only=True,
    ).active
    sap_limite = load_workbook(
        io.BytesIO(contenido_sap_limite),
        data_only=True,
    ).active
    assert solicitud_limite["F29"].value == "01/09/2026"
    assert solicitud_limite["I29"].value == "31/08/2026"
    assert sap_limite["G1"].value == "V101 01/09/2026 AL 31/08/2026 Gerente"
    assert sap_limite[f"H{sap_limite.max_row}"].value == sap_limite["G1"].value


def test_generar_polizas_rechaza_gastos_anteriores_al_cierre_previo() -> None:
    solicitud_id = uuid.uuid4()
    solicitud = {
        "store_id": "store-1",
        "period_id": "period-1",
        "reimbursement_starts_on": date(2026, 9, 27),
        "reimbursement_ends_on": date(2026, 9, 30),
        "previous_reimbursement_request_id": uuid.uuid4(),
        "previous_reimbursement_starts_on": date(2026, 9, 1),
        "previous_reimbursement_ends_on": date(2026, 9, 26),
        "previous_reimbursement_amount": "0",
        "created_at": datetime(2026, 10, 1, tzinfo=UTC),
        "folio": "TEST-2",
    }
    tienda = {"code": "V101"}
    periodo = {"id": "period-1"}
    gastos = [
        {
            "id": "stale-expense",
            "spent_on": date(2026, 9, 25),
        }
    ]
    resultados = []
    for valor in (solicitud, tienda, periodo, gastos):
        resultado = Mock()
        resultado.mappings.return_value.first.return_value = valor
        resultado.mappings.return_value.all.return_value = valor
        resultados.append(resultado)
    db = Mock()
    db.execute.side_effect = resultados
    db.scalar.return_value = date(2026, 9, 26)

    with (
        patch.object(macro_sap, "diccionario_tiendas", {"V101": {}}),
        pytest.raises(HTTPException) as exc_info,
    ):
        macro_sap.generar_polizas(
            solicitud_id,
            db=db,
            current_user=Mock(id=uuid.uuid4()),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "EXPENSE_OUTSIDE_PERIOD",
        "message": "El gasto está fuera de periodo.",
    }
