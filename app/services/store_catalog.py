import os

import pandas as pd

# store_catalog.py está en: /app/app/services/store_catalog.py
# Solo necesitamos subir 2 niveles para llegar a /app/app
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
RUTA_TIENDAS_EXCEL = os.path.join(
    ASSETS_DIR, "Copia de BASE DE TIENDAS.xlsx"
)


def cargar_catalogo_tiendas(ruta_archivo: str = RUTA_TIENDAS_EXCEL) -> dict:
    try:
        df = pd.read_excel(ruta_archivo, dtype=str).fillna("")
        df["TDA"] = df["TDA"].str.strip()

        return df.set_index("TDA").to_dict("index")

    except (OSError, ValueError, KeyError) as exc:
        print(f"Error al cargar catalogo de tiendas: {exc}")
        return {}


CATALOGO_TIENDAS = cargar_catalogo_tiendas()


def obtener_datos_excel_por_codigo(code: str) -> dict | None:
    codigo_normalizado = code.strip()

    if codigo_normalizado in CATALOGO_TIENDAS:
        return CATALOGO_TIENDAS[codigo_normalizado]

    codigo_sin_prefijo_hud = codigo_normalizado.removeprefix("HUD-")

    return CATALOGO_TIENDAS.get(codigo_sin_prefijo_hud)


def cargar_base_tiendas(ruta_archivo):
    try:
        df = pd.read_excel(ruta_archivo, dtype=str).fillna("")

        df["TDA"] = df["TDA"].str.strip()

        return df.set_index("TDA").to_dict("index")

    except Exception as e:  # noqa: BLE001
        print(f"❌ Error tiendas: {e}")
        return {}