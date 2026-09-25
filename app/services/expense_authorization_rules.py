from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.category_authorization_rule import CategoryAuthorizationRule
from app.services.authorization_areas import get_or_create_authorization_area

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

DEFAULT_CATEGORY_AUTHORIZATION_RULES = (
    {
        "category": "Agua",
        "requires_authorization": False,
        "area": None,
        "minimum_amount": None,
    },
    {
        "category": "Alimentos",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Artículos de Limpieza",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": Decimal("600.00"),
    },
    {
        "category": "Bolsas",
        "requires_authorization": True,
        "area": "Insumos",
        "minimum_amount": Decimal("50.00"),
    },
    {
        "category": "Energía Eléctrica",
        "requires_authorization": True,
        "area": "Contabilidad",
        "minimum_amount": None,
    },
    {
        "category": "Equipo de Cómputo Menor",
        "requires_authorization": True,
        "area": "Sistemas",
        "minimum_amount": None,
    },
    {
        "category": "Mantenimiento Equipo de Computo",
        "requires_authorization": True,
        "area": "Sistemas",
        "minimum_amount": None,
    },
    {
        "category": "Equipo Menor",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Extintores y Protección Civil",
        "requires_authorization": True,
        "area": "Gestoría",
        "minimum_amount": None,
    },
    {
        "category": "Gasolina",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Hospedaje",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Insumo",
        "requires_authorization": True,
        "area": "Insumos",
        "minimum_amount": None,
    },
    {
        "category": "Licencias y Permisos",
        "requires_authorization": True,
        "area": "Gestoría",
        "minimum_amount": None,
    },
    {
        "category": "Medicamentos",
        "requires_authorization": True,
        "area": "Gestoría",
        "minimum_amount": None,
    },
    {
        "category": "No Deducibles",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Papelería",
        "requires_authorization": True,
        "area": "Insumos",
        "minimum_amount": Decimal("600.00"),
    },
    {
        "category": "Paquetería y Mensajería",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Publicidad",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Recolección de Basura",
        "requires_authorization": True,
        "area": "Gestoría",
        "minimum_amount": None,
    },
    {
        "category": "Servicio de Agua",
        "requires_authorization": True,
        "area": "Servicio de Agua",
        "minimum_amount": None,
    },
    {
        "category": "Teléfono",
        "requires_authorization": True,
        "area": "Sistemas",
        "minimum_amount": None,
    },
    {
        "category": "Transportación",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Trasportación",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Transporte",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": None,
    },
    {
        "category": "Otros (merceria)",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": Decimal("100.00"),
    },
    {
        "category": "Otros",
        "requires_authorization": True,
        "area": "Supervisores",
        "minimum_amount": Decimal("100.00"),
    },
)

_TAXI_WORD_PATTERN = re.compile(r"\bTAXIS?\b")


@dataclass(frozen=True)
class ExpenseAuthorizationDecision:
    requires_authorization: bool
    authorization_area_id: UUID | None = None
    matched_rule: CategoryAuthorizationRule | None = None


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


def resolve_expense_authorization(
    db: Session,
    *,
    explicit: bool = False,
    category: str | None = None,
    amount: Decimal | float | str | None = None,
    description: str | None = None,
    merchant: str | None = None,
    authorization_area_id: UUID | None = None,
) -> ExpenseAuthorizationDecision:
    category_decision = _resolve_category_authorization(db, category=category, amount=amount)
    legacy_authorization = expense_requires_authorization(
        explicit=explicit,
        category=category,
        description=description,
        merchant=merchant,
    )
    requires_authorization = legacy_authorization or category_decision.requires_authorization
    resolved_area_id = authorization_area_id
    if resolved_area_id is None and category_decision.authorization_area_id is not None:
        resolved_area_id = category_decision.authorization_area_id

    return ExpenseAuthorizationDecision(
        requires_authorization=requires_authorization,
        authorization_area_id=resolved_area_id,
        matched_rule=category_decision.matched_rule,
    )


def ensure_default_category_authorization_rules(db: Session) -> None:
    existing_categories = set(
        db.scalars(select(CategoryAuthorizationRule.normalized_category)).all()
    )

    for rule_data in DEFAULT_CATEGORY_AUTHORIZATION_RULES:
        category = str(rule_data["category"])
        normalized_category = _normalize_text(category)
        if normalized_category in existing_categories:
            continue

        area_name = rule_data["area"]
        authorization_area_id = None
        if area_name:
            authorization_area = get_or_create_authorization_area(db, str(area_name))
            authorization_area_id = authorization_area.id

        db.add(
            CategoryAuthorizationRule(
                category=category,
                normalized_category=normalized_category,
                authorization_area_id=authorization_area_id,
                minimum_amount=rule_data["minimum_amount"],
                requires_authorization=bool(rule_data["requires_authorization"]),
                is_active=True,
                source="built_in",
            )
        )
        existing_categories.add(normalized_category)
    db.flush()


def _resolve_category_authorization(
    db: Session,
    *,
    category: str | None,
    amount: Decimal | float | str | None,
) -> ExpenseAuthorizationDecision:
    if not category:
        return ExpenseAuthorizationDecision(requires_authorization=False)

    ensure_default_category_authorization_rules(db)
    normalized_category = _normalize_text(category)
    if not normalized_category:
        return ExpenseAuthorizationDecision(requires_authorization=False)

    rule = db.scalar(
        select(CategoryAuthorizationRule)
        .options(selectinload(CategoryAuthorizationRule.authorization_area))
        .where(
            CategoryAuthorizationRule.normalized_category == normalized_category,
            CategoryAuthorizationRule.is_active.is_(True),
        )
    )
    if rule is None:
        return ExpenseAuthorizationDecision(requires_authorization=False)

    if not rule.requires_authorization:
        return ExpenseAuthorizationDecision(
            requires_authorization=False,
            matched_rule=rule,
        )

    amount_value = _amount_or_none(amount)
    if (
        rule.minimum_amount is not None
        and amount_value is not None
        and amount_value < Decimal(rule.minimum_amount)
    ):
        return ExpenseAuthorizationDecision(
            requires_authorization=False,
            matched_rule=rule,
        )

    return ExpenseAuthorizationDecision(
        requires_authorization=True,
        authorization_area_id=rule.authorization_area_id,
        matched_rule=rule,
    )


def _amount_or_none(value: Decimal | float | str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:  # noqa: BLE001
        return None


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
