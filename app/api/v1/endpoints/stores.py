from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.store import Store, StoreUserAssignment
from app.models.user import User
from app.schemas.store import StoreCreate, StoreRead, StoreUpdate
from app.schemas.store_assignment import StoreUserAssignmentCreate, StoreUserAssignmentRead

router = APIRouter()


@router.post("/", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
def create_store(store_in: StoreCreate, db: Annotated[Session, Depends(get_db)]) -> Store:
    store = Store(**store_in.model_dump())
    db.add(store)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Store code already exists",
        ) from exc
    db.refresh(store)
    return store


@router.get("/", response_model=list[StoreRead])
def list_stores(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Store]:
    statement = select(Store).order_by(Store.code).limit(limit).offset(offset)
    return list(db.scalars(statement))


@router.get("/{store_id}", response_model=StoreRead)
def get_store(store_id: UUID, db: Annotated[Session, Depends(get_db)]) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return store


@router.post(
    "/{store_id}/users",
    response_model=StoreUserAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_user_to_store(
    store_id: UUID,
    assignment_in: StoreUserAssignmentCreate,
    db: Annotated[Session, Depends(get_db)],
) -> StoreUserAssignment:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    user = db.get(User, assignment_in.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "INACTIVE_USER", "message": "Cannot assign an inactive user"},
        )
    if user.role != assignment_in.role:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "ASSIGNMENT_ROLE_MISMATCH",
                "message": "Assignment role must match the user's role",
            },
        )

    assignment = db.scalar(
        select(StoreUserAssignment).where(
            StoreUserAssignment.store_id == store_id,
            StoreUserAssignment.user_id == assignment_in.user_id,
        )
    )
    if assignment is None:
        assignment = StoreUserAssignment(
            store_id=store_id,
            user_id=assignment_in.user_id,
            role=assignment_in.role,
            is_active=assignment_in.is_active,
        )
        db.add(assignment)
    else:
        assignment.role = assignment_in.role
        assignment.is_active = assignment_in.is_active

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_STORE_USER_ASSIGNMENT",
                "message": "User is already assigned to this store",
            },
        ) from exc
    db.refresh(assignment)
    return assignment


@router.get("/{store_id}/users", response_model=list[StoreUserAssignmentRead])
def list_store_user_assignments(
    store_id: UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[StoreUserAssignment]:
    if db.get(Store, store_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    statement = (
        select(StoreUserAssignment)
        .where(StoreUserAssignment.store_id == store_id)
        .order_by(StoreUserAssignment.created_at.desc())
    )
    return list(db.scalars(statement))


@router.patch("/{store_id}", response_model=StoreRead)
def update_store(
    store_id: UUID,
    store_in: StoreUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Store:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    updates = store_in.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(store, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Store code already exists",
        ) from exc
    db.refresh(store)
    return store
