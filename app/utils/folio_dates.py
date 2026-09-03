import re
from datetime import date, datetime


def obtener_fecha_desde_folio(folio: str) -> date:
    folio = str(folio).strip().upper()

    coincidencia = re.fullmatch(
        r"[A-Z0-9]{4}-(\d{8})\d+",
        folio,
    )

    if coincidencia is None:
        raise ValueError(
            f"Formato de folio inválido: {folio}"
        )

    fecha_texto = coincidencia.group(1)

    return datetime.strptime(
        fecha_texto,
        "%d%m%Y",
    ).date()