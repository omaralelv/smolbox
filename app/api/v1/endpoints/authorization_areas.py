from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies.auth import get_current_user, require_roles
from app.db.session import get_db
from app.models.authorization_area import AuthorizationArea, UserAuthorizationArea
from app.models.user import User, UserRole
from app.schemas.authorization_area import (
    AuthorizationAreaCreate,
    AuthorizationAreaRead,
    UserAuthorizationAreaCreate,
    UserAuthorizationAreaRead,
)
from app.services.authorization_areas import get_or_create_authorization_area

router = APIRouter()


@router.get("/", response_model=list[AuthorizationAreaRead])
def list_authorization_areas(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AuthorizationArea]:
    del current_user
    return list(db.scalars(select(AuthorizationArea).order_by(AuthorizationArea.name)))


@router.post("/", response_model=AuthorizationAreaRead, status_code=status.HTTP_201_CREATED)
def create_authorization_area(
    area_in: AuthorizationAreaCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
) -> AuthorizationArea:
    del current_user
    try:
        area = get_or_create_authorization_area(
            db,
            area_in.name,
            is_active=area_in.is_active,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "AUTHORIZATION_AREA_CONFLICT",
                "message": "Authorization area could not be saved.",
            },
        ) from exc
    db.refresh(area)
    return area


@router.get("/users/{user_id}", response_model=list[UserAuthorizationAreaRead])
def list_user_authorization_areas(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
) -> list[UserAuthorizationArea]:
    del current_user
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    statement = (
        select(UserAuthorizationArea)
        .options(selectinload(UserAuthorizationArea.authorization_area))
        .where(UserAuthorizationArea.user_id == user_id)
        .order_by(UserAuthorizationArea.created_at.desc())
    )
    return list(db.scalars(statement))


@router.post(
    "/users/{user_id}",
    response_model=UserAuthorizationAreaRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_authorization_area_to_user(
    user_id: UUID,
    assignment_in: UserAuthorizationAreaCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
) -> UserAuthorizationArea:
    del current_user
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role != UserRole.authorizer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "USER_NOT_AUTHORIZER",
                "message": "Only authorizer users can be assigned to authorization areas.",
            },
        )

    area = _resolve_authorization_area(assignment_in, db)
    assignment = db.scalar(
        select(UserAuthorizationArea).where(
            UserAuthorizationArea.user_id == user.id,
            UserAuthorizationArea.authorization_area_id == area.id,
        )
    )
    if assignment is None:
        assignment = UserAuthorizationArea(
            user_id=user.id,
            authorization_area_id=area.id,
            is_active=assignment_in.is_active,
        )
        db.add(assignment)
    else:
        assignment.is_active = assignment_in.is_active

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "USER_AUTHORIZATION_AREA_CONFLICT",
                "message": "User authorization area assignment could not be saved.",
            },
        ) from exc
    db.refresh(assignment)
    return db.scalars(
        select(UserAuthorizationArea)
        .options(selectinload(UserAuthorizationArea.authorization_area))
        .where(UserAuthorizationArea.id == assignment.id)
    ).one()


def _resolve_authorization_area(
    assignment_in: UserAuthorizationAreaCreate,
    db: Session,
) -> AuthorizationArea:
    if assignment_in.authorization_area_id is not None:
        area = db.get(AuthorizationArea, assignment_in.authorization_area_id)
        if area is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Authorization area not found",
            )
        return area

    try:
        return get_or_create_authorization_area(
            db,
            assignment_in.authorization_area_name or "",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "AUTHORIZATION_AREA_NAME_INVALID",
                "message": str(exc),
            },
        ) from exc
