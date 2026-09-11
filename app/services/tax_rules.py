import pandas as pd
from decimal import Decimal


def cargar_tipo_gastos(ruta_archivo):
    try:
        df = pd.read_excel(ruta_archivo, dtype=str).fillna("")

        df["CODIGO"] = df["CODIGO"].str.strip()
        df["TIPO_GASTO"] = df["TIPO_GASTO"].str.strip()

        if df["CODIGO"].duplicated().any():
            duplicados = df.loc[
                df["CODIGO"].duplicated(keep=False), "CODIGO"
            ].tolist()

            raise ValueError(
                f"Códigos contables duplicados en el catálogo: {duplicados}"
            )

        return df.set_index("CODIGO").to_dict("index")

    except Exception as e:  # noqa: BLE001
        print(f"❌ Error gastos: {e}")
        return {}


def normalizar_texto(valor):
    return " ".join(str(valor or "").strip().casefold().split())


def crear_indice_categorias(diccionario_gastos):
    """
    Convierte:

    {
        "601001": {"TIPO_GASTO": "Papelería"}
    }

    en:

    {
        "papelería": {
            "codigo": "601001",
            "descripcion": "Papelería"
        }
    }
    """
    indice = {}

    for codigo, datos in diccionario_gastos.items():
        descripcion = datos.get("TIPO_GASTO", "").strip()

        if not descripcion:
            continue

        clave = normalizar_texto(descripcion)

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
) -> tuple[Decimal, str]:
    descripcion_normalizada = normalizar_texto(descripcion)

    # Tiendas incluidas en el archivo W6
    # if normalizar_texto(numero_tienda) in tiendas_iva_w6:
    #    return Decimal("8"), "W6"

    # Pasajes y taxis siempre usa 0% y W2
    if descripcion_normalizada == normalizar_texto("Pasajes y taxis"):
        return Decimal(0), "W2"

    # Forzar No Deducibles a 0%: W0
    if descripcion_normalizada == normalizar_texto("No Deducibles"):
        return Decimal(0), "W0"

    # Cualquier gasto que tenga 0% usa W0
    if porcentaje_iva == Decimal(0):
        return Decimal(0), "W0"

    if porcentaje_iva == Decimal(16):
        return Decimal(16), "W1"

    # Regla 4: Regla general
    return porcentaje_iva, "W1"