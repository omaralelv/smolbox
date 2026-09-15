from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.services.initial_catalog_import import import_initial_catalog
from app.services.store_catalog import RUTA_TIENDAS_EXCEL


def main() -> None:
    args = _parse_args()
    db = SessionLocal()
    try:
        result = import_initial_catalog(db, args.excel, password=args.password)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Importación inicial completada.")
    print(f"Usuarios creados: {len(result.created_users)}")
    print(f"Usuarios omitidos por existir: {len(set(result.skipped_users))}")
    print(f"Tiendas creadas: {len(result.created_stores)}")
    print(f"Tiendas omitidas por existir: {len(set(result.skipped_stores))}")
    print(f"Asignaciones creadas: {result.created_assignments}")
    _print_items("Filas inválidas", result.invalid_rows)
    _print_items("Conflictos", result.conflicts)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create initial users, stores and store assignments from the Excel catalog."
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=Path(RUTA_TIENDAS_EXCEL),
        help="Path to the Excel catalog.",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Optional temporary password for newly created users.",
    )
    return parser.parse_args()


def _print_items(label: str, items: list[str]) -> None:
    print(f"{label}: {len(items)}")
    for item in items:
        print(f"  - {item}")


if __name__ == "__main__":
    main()
