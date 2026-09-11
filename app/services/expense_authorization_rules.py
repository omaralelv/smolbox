from __future__ import annotations

import re
import unicodedata

TAXI_AUTHORIZATION_TYPES = (
    "TAXI PARA REALIZAR PAGO DEL SERVICIO DE AGUA",
    "TAXI PARA IR A GESTINAR ALGUN TRAMITE RELACIONADO AL SERVICIO DE AGUA",
    "TAXI PARA REALIZAR TRAMITES Y O PAGOS AL MUNICIPIO",
    "TAXI PARA REALIZAR TRAMITES Y O PAGOS A PROTECCION CIVIL",
    "TAXI PARA REALIZAR TRAMITE Y O PAGO A SECRETARIA DEL TRABAJO",
    "TAXI PARA REALIZAR TRAMITE Y O PAGO A SECRETARIA DE FINANZAS",
    "TAXI PARA REALIZAR TRAMITE Y O PAGO AL IMSS",
    "TAXI NOCTURNO PARA EL PERSONAL QUE SE QUEDA A ESPERAR EL CAMION DE LA MERCANCIA",
    "TAXI POR TRAMITE Y O PAGO A TEMA DE LA LUZ CFE",
    "TAXI PARA EL PERSONAL QUE SALE TARDE DE LA TIENDA",
    "TAXI PARA EL PERSONAL QUE VA DE APOYO A OTRA TIENDA",
    "TAXI PARA EL PERSONAL QUE SE QUEDA A INVENTARIOS",
    "TAXIS POR TRASPASOS DE MERCANCIA A OTRAS TIENDAS",
    "TAXIS POR TRASPASOS DE MUEBLES A OTRAS TIENDAS",
    "TAXIS POR CAMBACEOS",
    "TAXI POR EL PERSONAS QUE REALIZA LA COMPRA DE INSUMOS DE TIENDA",
    "TAXI POR TRASLADO DE ALGUN EQUIPO DE COMPUTO A OTRAS TIENDAS",
    "TAXI POR TRASLADO DE ALGUN EQUIPO DE COMPUTO AL LUGAR DEL SERVICIO DE REPARACION",
    "TAXIS POR IR A LA PROCURADURIA DEMANDA ROBO EN TDA",
)

TAXI_CATEGORY_ALIASES = (
    "PASAJES Y TAXIS",
    "TAXIS",
    "TAXI",
)

_TAXI_WORD_PATTERN = re.compile(r"\bTAXIS?\b")


def expense_requires_authorization(
    *,
    explicit: bool = False,
    category: str | None = None,
    description: str | None = None,
    merchant: str | None = None,
) -> bool:
    if explicit:
        return True

    values = [
        _normalize_text(value)
        for value in (category, description, merchant)
        if value is not None
    ]
    return any(_matches_taxi_authorization_rule(value) for value in values)


def _matches_taxi_authorization_rule(value: str) -> bool:
    if not value:
        return False

    if value in _NORMALIZED_CATEGORY_ALIASES:
        return True

    if _TAXI_WORD_PATTERN.search(value):
        return True

    return any(_matches_known_taxi_type(value, rule) for rule in _NORMALIZED_TAXI_TYPES)


def _matches_known_taxi_type(value: str, rule: str) -> bool:
    if value == rule:
        return True
    if rule in value:
        return True
    return len(value) >= 20 and value in rule


def _normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", without_accents.upper())
    return re.sub(r"\s+", " ", normalized).strip()


_NORMALIZED_TAXI_TYPES = tuple(_normalize_text(item) for item in TAXI_AUTHORIZATION_TYPES)
_NORMALIZED_CATEGORY_ALIASES = tuple(_normalize_text(item) for item in TAXI_CATEGORY_ALIASES)
