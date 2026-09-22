from typing import Annotated
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.audit_log import AuditActorType, AuditLog
from app.models.authorization_area import UserAuthorizationArea
from app.models.store import StoreUserAssignment
from app.models.user import User
from app.schemas.user import UserCreate, UserDelete, UserRead, UserUpdate
from app.services.cognito import CognitoSyncError, CognitoUserSync
from app.services.security import hash_password

router = APIRouter()


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    _ensure_email_available(db, user_in.email)
    user_data = user_in.model_dump(exclude={"password"})
    if user_in.password:
        user_data["password_hash"] = hash_password(user_in.password)
    user = User(**user_data)
    cognito_sub = _ensure_cognito_user(settings, user, password=user_in.password)
    if cognito_sub:
        user.cognito_sub = cognito_sub
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_USER_EMAIL", "message": "User email already exists"},
        ) from exc
    db.refresh(user)
    return user


@router.get("/", response_model=list[UserRead])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    statement = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement))


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Annotated[Session, Depends(get_db)]) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    previous_email = user.email
    updates = user_in.model_dump(exclude_unset=True)
    password = updates.pop("password", None)
    next_email = updates.get("email")
    if next_email and next_email != user.email:
        _ensure_email_available(db, next_email, exclude_user_id=user.id)

    for field, value in updates.items():
        setattr(user, field, value)
    if password:
        user.password_hash = hash_password(password)
    if updates.get("is_active") is False:
        _deactivate_user_assignments(user.id, db)
    cognito_sub = _ensure_cognito_user(settings, user, password=password)
    if cognito_sub:
        user.cognito_sub = cognito_sub
    if settings.cognito_enabled and previous_email != user.email:
        _delete_cognito_user(settings, previous_email)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_USER_EMAIL", "message": "User email already exists"},
        ) from exc
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    delete_in: UserDelete,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user_payload = {
        "target_user_id": str(user.id),
        "target_user_email": user.email,
        "target_user_role": user.role.value,
        "reason": delete_in.reason,
    }
    _delete_user_assignments(user.id, db)
    db.add(
        AuditLog(
            actor_type=AuditActorType.system,
            action="user_deleted",
            message=delete_in.reason,
            event_payload=user_payload,
        )
    )
    _delete_cognito_user(settings, user.email)
    db.delete(user)
    db.commit()


@router.post("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    _ensure_cognito_user(settings, user)
    _deactivate_user_assignments(user.id, db)
    db.commit()
    db.refresh(user)
    return user


def _deactivate_user_assignments(user_id: UUID, db: Session) -> None:
    db.execute(
        update(StoreUserAssignment)
        .where(StoreUserAssignment.user_id == user_id)
        .values(is_active=False)
    )
    db.execute(
        update(UserAuthorizationArea)
        .where(UserAuthorizationArea.user_id == user_id)
        .values(is_active=False)
    )


def _delete_user_assignments(user_id: UUID, db: Session) -> None:
    db.execute(sa_delete(StoreUserAssignment).where(StoreUserAssignment.user_id == user_id))
    db.execute(sa_delete(UserAuthorizationArea).where(UserAuthorizationArea.user_id == user_id))


def _ensure_email_available(
    db: Session,
    email: str,
    *,
    exclude_user_id: UUID | None = None,
) -> None:
    statement = select(User).where(User.email == email)
    if exclude_user_id is not None:
        statement = statement.where(User.id != exclude_user_id)
    if db.scalar(statement) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_USER_EMAIL", "message": "User email already exists"},
        )


def _ensure_cognito_user(
    settings: Settings,
    user: User,
    *,
    password: str | None = None,
) -> str | None:
    if not settings.cognito_enabled:
        return None
    try:
        return CognitoUserSync(settings).ensure_user(user, password=password)
    except (BotoCoreError, ClientError, CognitoSyncError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "COGNITO_SYNC_FAILED",
                "message": "No se pudo sincronizar el usuario con Cognito.",
            },
        ) from exc


def _delete_cognito_user(settings: Settings, email: str) -> None:
    if not settings.cognito_enabled:
        return
    try:
        CognitoUserSync(settings).delete_user(email)
    except (BotoCoreError, ClientError, CognitoSyncError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "COGNITO_SYNC_FAILED",
                "message": "No se pudo sincronizar el usuario con Cognito.",
            },
        ) from exc
