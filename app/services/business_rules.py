from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_rule import BusinessRule

DEFAULT_BUSINESS_RULES = [
    {
        "code": "authorization_threshold",
        "name": "Monto que requiere autorizacion",
        "description": "Monto minimo a partir del cual un gasto debe pasar por autorizacion.",
        "value": {"amount": "1000.00", "currency": "MXN"},
    },
    {
        "code": "require_cfdi_for_accounting",
        "name": "CFDI obligatorio para contabilidad",
        "description": "Define si contabilidad puede cerrar revision sin CFDI vigente y valido.",
        "value": {"enabled": True},
    },
    {
        "code": "block_out_of_period_expenses",
        "name": "Bloquear gastos fuera de periodo",
        "description": "Define si tienda/importacion deben bloquear gastos fuera del periodo.",
        "value": {"enabled": True},
    },
    {
        "code": "auto_adjust_total_on_removed_expense",
        "name": "Ajustar total al quitar gasto",
        "description": "Define si el total reportado se ajusta automaticamente al quitar un gasto.",
        "value": {"enabled": True},
    },
]


def ensure_default_business_rules(db: Session) -> None:
    existing_codes = set(db.scalars(select(BusinessRule.code)))
    for rule in DEFAULT_BUSINESS_RULES:
        if rule["code"] in existing_codes:
            continue
        db.add(BusinessRule(**rule, is_active=True))
    db.flush()
