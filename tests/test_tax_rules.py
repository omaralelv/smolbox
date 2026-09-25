import pytest
from openpyxl import Workbook

from app.services.tax_rules import cargar_tipo_gastos, crear_indice_categorias


def test_catalogo_permite_mismo_codigo_para_categorias_distintas(tmp_path) -> None:
    catalogo = tmp_path / "TiposGastos.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["CODIGO", "TIPO_GASTO"])
    worksheet.append(["601007", "Insumos"])
    worksheet.append(["601007", "Papelería"])
    workbook.save(catalogo)

    gastos = cargar_tipo_gastos(catalogo)
    indice = crear_indice_categorias(gastos)

    assert indice["insumos"] == {
        "codigo": "601007",
        "descripcion": "Insumos",
    }
    assert indice["papelería"] == {
        "codigo": "601007",
        "descripcion": "Papelería",
    }


def test_indice_rechaza_descripciones_duplicadas_sin_importar_mayusculas() -> None:
    gastos = [
        {"CODIGO": "601007", "TIPO_GASTO": "Insumos"},
        {"CODIGO": "601008", "TIPO_GASTO": " INSUMOS "},
    ]

    with pytest.raises(ValueError, match="TIPO_GASTO duplicado"):
        crear_indice_categorias(gastos)
