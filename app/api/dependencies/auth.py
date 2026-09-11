from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.security import InvalidToken, parse_access_token, parse_cognito_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_REQUIRED", "message": "Bearer token is required"},
        )
    token = credentials.credentials
    user = None
    try:
        user_id = parse_access_token(token, settings)
        user = db.get(User, user_id)
    except InvalidToken:
        if settings.cognito_enabled:
            try:
                cognito_sub = parse_cognito_token(token, settings)
            except (InvalidToken, ValueError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"code": "INVALID_TOKEN", "message": str(exc)},
                ) from exc
            user = db.scalar(select(User).where(User.cognito_sub == cognito_sub))

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "User is not active"},
        )
    return user


def require_roles(*roles: UserRole):
    allowed_roles = set(roles)

    def dependency(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN_ROLE",
                    "message": f"Role {current_user.role.value} is not allowed",
                },
            )
        return current_user

    return dependency
