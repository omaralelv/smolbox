from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.store import Store
from app.models.store_spending_baseline import StoreSpendingBaseline


BASE_DIR = Path(__file__).resolve().parents[1]

RUTA_EXCEL = (
    BASE_DIR
    / "assets"
    / "COPIA SALDO DE TDAS ANOS 24 25 Y 26.xlsx"
)

HOJA_EXCEL = "PRESUPUESTO 2024-2026"


def limpiar_codigo_tienda(valor) -> str:
    if valor is None:
        return ""

    codigo = str(valor).strip().upper()

    if codigo.endswith(".0"):
        codigo = codigo[:-2]

    return codigo


def convertir_decimal(valor) -> Decimal:
    if valor is None:
        return Decimal("0.00")

    texto = str(valor).strip()

    if not texto or texto.lower() == "nan":
        return Decimal("0.00")

    texto = (
        texto
        .replace("\u00A0", "")
        .replace("$", "")
        .replace(",", "")
    )

    if texto.startswith("(") and texto.endswith(")"):
        texto = f"-{texto[1:-1]}"

    return Decimal(texto).quantize(
        Decimal("0.01")
    )


def obtener_o_crear_baseline(
    db,
    store_id,
    fiscal_year: int,
    historical_amount: Decimal,
    baseline_as_of: date,
) -> None:
    baseline = db.scalar(
        select(StoreSpendingBaseline).where(
            StoreSpendingBaseline.store_id == store_id,
            StoreSpendingBaseline.fiscal_year == fiscal_year,
        )
    )

    if baseline is None:
        baseline = StoreSpendingBaseline(
            store_id=store_id,
            fiscal_year=fiscal_year,
            historical_amount=historical_amount,
            baseline_as_of=baseline_as_of,
            source="excel_import",
        )

        db.add(baseline)
        return

    baseline.historical_amount = historical_amount
    baseline.baseline_as_of = baseline_as_of
    baseline.source = "excel_import"


def importar_historico() -> None:
    print(f"Buscando archivo en: {RUTA_EXCEL}")

    if not RUTA_EXCEL.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo Excel en: {RUTA_EXCEL}"
        )

    df = pd.read_excel(
        RUTA_EXCEL,
        sheet_name=HOJA_EXCEL,
        header=None,
        usecols="A,C,D,E",
        dtype=str,
    ).fillna("")

    print("Filas leídas originalmente:", len(df))
    print("Primeras filas:")
    print(df.head(10).to_string())

    df.columns = [
        "TDA",
        "GASTO_2024",
        "GASTO_2025",
        "GASTO_2026",
    ]

    df["TDA"] = df["TDA"].map(
        limpiar_codigo_tienda
    )

    print("Códigos detectados antes del filtro:")
    print(df["TDA"].head(20).tolist())

    df = df[
        df["TDA"].str.fullmatch(
            r"^[A-Z]+\d+$",
            case=False,
            na=False,
        )
    ].copy()

    print(
        "Filas válidas después del filtro:",
        len(df),
    )

    print(
        "Códigos válidos:",
        df["TDA"].tolist(),
    )

    db = SessionLocal()

    tiendas_no_encontradas = []
    tiendas_importadas = []

    try:
        for _, fila in df.iterrows():
            codigo_tienda = fila["TDA"]

            print(
                f"Buscando en SQL: {codigo_tienda!r}"
            )

            tienda = db.scalar(
                select(Store).where(
                    Store.code == codigo_tienda
                )
            )

            if tienda is None:
                print(
                    f"No encontrada en SQL: "
                    f"{codigo_tienda!r}"
                )

                tiendas_no_encontradas.append(
                    codigo_tienda
                )
                continue

            print(
                f"Encontrada: "
                f"{tienda.code!r} - {tienda.name}"
            )

            obtener_o_crear_baseline(
                db=db,
                store_id=tienda.id,
                fiscal_year=2024,
                historical_amount=convertir_decimal(
                    fila["GASTO_2024"]
                ),
                baseline_as_of=date(2024, 12, 31),
            )

            obtener_o_crear_baseline(
                db=db,
                store_id=tienda.id,
                fiscal_year=2025,
                historical_amount=convertir_decimal(
                    fila["GASTO_2025"]
                ),
                baseline_as_of=date(2025, 12, 31),
            )

            obtener_o_crear_baseline(
                db=db,
                store_id=tienda.id,
                fiscal_year=2026,
                historical_amount=convertir_decimal(
                    fila["GASTO_2026"]
                ),
                baseline_as_of=date(2026, 8, 31),
            )

            tiendas_importadas.append(codigo_tienda)

        db.commit()

        print("✅ Importación completada.")
        print(
            "Tiendas importadas:",
            len(tiendas_importadas),
        )

        if tiendas_no_encontradas:
            print(
                "⚠️ Tiendas del Excel que no existen "
                "en SQL:"
            )
            print(
                ", ".join(tiendas_no_encontradas)
            )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    importar_historico()