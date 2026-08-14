from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenRead
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
