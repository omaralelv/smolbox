from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.business_rule import BusinessRule
from app.models.user import User, UserRole
from app.schemas.business_rule import BusinessRuleRead, BusinessRuleUpdate
from app.services.business_rules import ensure_default_business_rules

router = APIRouter()


@router.get("/", response_model=list[BusinessRuleRead])
def list_business_rules(
    db: Annotated[Session, Depends(get_db)],
) -> list[BusinessRule]:
    ensure_default_business_rules(db)
    db.commit()
    return list(db.scalars(select(BusinessRule).order_by(BusinessRule.code)))


@router.patch("/{rule_code}", response_model=BusinessRuleRead)
def update_business_rule(
    rule_code: str,
    rule_in: BusinessRuleUpdate,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
) -> BusinessRule:
    ensure_default_business_rules(db)
    rule = db.scalar(select(BusinessRule).where(BusinessRule.code == rule_code))
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business rule not found")

    updates = rule_in.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule
