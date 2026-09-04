from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.period import Period, PeriodStatus
from app.models.store import Store, StoreUserAssignment
from app.models.user import User, UserRole
from app.schemas.auth import AuthContextRead, LoginRequest, StoreContextRead, TokenRead
from app.schemas.user import UserRead
from app.services.security import create_access_token, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenRead)
def login(
    login_in: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenRead:
    user = db.scalar(select(User).where(User.email == login_in.email.lower()))
    if user is None or not user.is_active or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Invalid email or password"},
        )

    access_token, expires_at = create_access_token(user.id, settings)
    return TokenRead(access_token=access_token, expires_at=expires_at, user=user)


@router.get("/me", response_model=UserRead)
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.get("/me/context", response_model=AuthContextRead)
def read_my_context(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthContextRead:
    stores = _context_stores_for_user(current_user, db)
    return AuthContextRead(
        user=current_user,
        stores=stores,
        active_store=stores[0] if stores else None,
        current_period=_current_open_period(db),
    )


def _context_stores_for_user(current_user: User, db: Session) -> list[StoreContextRead]:
    if current_user.role == UserRole.admin:
        return [
            _store_context(store, assignment_role=None, is_active_assignment=True)
            for store in db.scalars(select(Store).order_by(Store.code).limit(200))
        ]

    assignments = db.scalars(
        select(StoreUserAssignment)
        .options(selectinload(StoreUserAssignment.store))
        .where(
            StoreUserAssignment.user_id == current_user.id,
            StoreUserAssignment.is_active.is_(True),
        )
        .order_by(StoreUserAssignment.created_at.desc())
    )
    return [
        _store_context(
            assignment.store,
            assignment_role=assignment.role,
            is_active_assignment=assignment.is_active,
        )
        for assignment in assignments
    ]


def _store_context(
    store: Store,
    *,
    assignment_role: UserRole | None,
    is_active_assignment: bool,
) -> StoreContextRead:
    return StoreContextRead(
        id=store.id,
        code=store.code,
        name=store.name,
        contact_email=store.contact_email,
        assigned_accountant=store.assigned_accountant,
        manager_name=store.manager_name,
        bank_account=store.bank_account,
        state_region=store.state_region,
        assignment_role=assignment_role,
        is_active_assignment=is_active_assignment,
    )


def _current_open_period(db: Session) -> Period | None:
    today = datetime.now(UTC).date()
    period = db.scalar(
        select(Period)
        .where(
            Period.status == PeriodStatus.open,
            Period.starts_on <= today,
            Period.ends_on >= today,
        )
        .order_by(Period.starts_on.desc())
    )
    if period is not None:
        return period
    return db.scalar(
        select(Period)
        .where(Period.status == PeriodStatus.open)
        .order_by(Period.starts_on.desc())
    )
