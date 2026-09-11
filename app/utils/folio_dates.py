import re
from datetime import date, datetime


def obtener_fecha_desde_folio(folio: str) -> date:
    """
    Extrae la fecha DDMMYYYY de un folio.

    Ejemplos:
    A001-010920262     -> 2026-09-01
    V001-090920261     -> 2026-09-09
    HUD-A001-031020261 -> 2026-10-03
    """
    folio_limpio = str(folio or "").strip().upper()

    coincidencia = re.fullmatch(
        r"^.+-(\d{8})\d+$",
        folio_limpio,
    )

    if coincidencia is None:
        raise ValueError(
            "Formato de folio inválido: "
            f"{folio_limpio!r}. "
            "Se esperaba PREFIJO-DDMMYYYYCONSECUTIVO."
        )

    fecha_texto = coincidencia.group(1)

    try:
        return datetime.strptime(
            fecha_texto,
            "%d%m%Y",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "El folio contiene una fecha inválida: "
            f"{fecha_texto!r}."
        ) from exc