from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pandas as pd


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
TIENDAS_IVA_W6_FILES = (
    "tiendas_iva_w6.xlsx",
    "TDAS IVA W6.xlsx",
)


def cargar_tipo_gastos(ruta_archivo):
    try:
        df = pd.read_excel(ruta_archivo, dtype=str).fillna("")

        df["CODIGO"] = df["CODIGO"].str.strip()
        df["TIPO_GASTO"] = df["TIPO_GASTO"].str.strip()

        return df.to_dict("records")

    except Exception as e:  # noqa: BLE001
        print(f"❌ Error gastos: {e}")
        return {}


def normalizar_texto(valor):
    return " ".join(str(valor or "").strip().casefold().split())


PASAJES_TAXIS_IVA_CERO = tuple(
    normalizar_texto(valor)
    for valor in (
        "Pasajes y taxis",
    )
)

AGUA_IVA_CERO = tuple(
    normalizar_texto(valor)
    for valor in (
        "Agua",
    )
)

HOSPEDAJE_IVA_CERO = tuple(
    normalizar_texto(valor)
    for valor in (
        "Hospedaje",
    )
)

NO_DEDUCIBLES_IVA_CERO = tuple(
    normalizar_texto(valor)
    for valor in (
        "No Deducibles",
        "No Deducible",
        "No Dedusibles",
        "No Dedusible",
        "Sin Deducibles",
        "Sin Deducible",
    )
)

AGUA_IVA_CERO = tuple(
    normalizar_texto(valor)
    for valor in (
        "Agua",
        "Servicio de Agua",
    )
)


def crear_indice_categorias(diccionario_gastos):
    """
    Convierte:

    [
        {"CODIGO": "601001", "TIPO_GASTO": "Papelería"}
    ]

    en:

    {
        "papelería": {
            "codigo": "601001",
            "descripcion": "Papelería"
        }
    }
    """
    indice = {}

    for datos in diccionario_gastos:
        descripcion = datos.get("TIPO_GASTO", "").strip()

        if not descripcion:
            continue

        clave = normalizar_texto(descripcion)
        codigo = datos.get("CODIGO", "").strip()

        if clave in indice:
            raise ValueError(
                f"TIPO_GASTO duplicado en TiposGastos.xlsx: {descripcion}"
            )

        indice[clave] = {
            "codigo": codigo,
            "descripcion": descripcion,
        }

    return indice


## Para cargar tiendas del 8% de IVA
def cargar_tiendas_iva_w6(ruta_archivo):
    try:
        df = pd.read_excel(
            ruta_archivo,
            dtype=str,
            usecols=["TIENDA"],
        ).fillna("")

        df["TIENDA"] = df["TIENDA"].str.strip()

        return {
            normalizar_texto(tienda)
            for tienda in df["TIENDA"]
            if tienda
        }

    except Exception as e:  # noqa: BLE001
        print(f"❌ Error al cargar tiendas con IVA W6: {e}")
        return set()


def determinar_iva_e_indice(
    descripcion: str,
    numero_tienda: str,
    porcentaje_iva: Decimal,
    tiendas_iva_w6: set[str] | None = None,
) -> tuple[Decimal, str]:
    descripcion_normalizada = normalizar_texto(descripcion)

    # Agua siempre usa 0% y W0
    if descripcion_normalizada in AGUA_IVA_CERO:
        return Decimal(0), "W0"

    # Tiendas incluidas en el archivo W6
    if tiendas_iva_w6 and normalizar_texto(numero_tienda) in tiendas_iva_w6:
        return Decimal("8"), "W6"

    # Pasajes y taxis siempre usa 0% y W2
    if descripcion_normalizada in PASAJES_TAXIS_IVA_CERO:
        return Decimal(0), "W2"

    # HOSPEDAJE siempre usa 0% y W0
    if descripcion_normalizada in HOSPEDAJE_IVA_CERO:
        return Decimal(0), "W0"

    # AGUA siempre usa 0% y W0
    if descripcion_normalizada in AGUA_IVA_CERO:
        return Decimal(0), "W0"

    # Forzar No Deducibles a 0%: W0
    if descripcion_normalizada in NO_DEDUCIBLES_IVA_CERO:
        return Decimal(0), "W0"

    # Regla 4: Regla general
    return porcentaje_iva, "W1"


def determinar_tasa_iva_para_gasto(
    *,
    descripcion: str,
    numero_tienda: str,
    porcentaje_iva: Decimal | float | str | None,
    tiendas_iva_w6: set[str] | None = None,
) -> Decimal:
    porcentaje_base = normalizar_porcentaje_iva(porcentaje_iva)
    if porcentaje_base is None:
        porcentaje_base = Decimal("16.00")

    tasa_iva, _indice_iva = determinar_iva_e_indice(
        descripcion=descripcion,
        numero_tienda=numero_tienda,
        porcentaje_iva=porcentaje_base,
        tiendas_iva_w6=tiendas_iva_w6 if tiendas_iva_w6 is not None else tiendas_iva_w6_default(),
    )
    tasa_normalizada = normalizar_porcentaje_iva(tasa_iva)
    return tasa_normalizada if tasa_normalizada is not None else Decimal("16.00")


def normalizar_porcentaje_iva(value: Decimal | float | str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def tiendas_iva_w6_default() -> set[str]:
    for filename in TIENDAS_IVA_W6_FILES:
        path = ASSETS_DIR / filename
        if path.exists():
            return cargar_tiendas_iva_w6(str(path))
    return set()
