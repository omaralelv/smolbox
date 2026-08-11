from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.store import Store
from app.schemas.store import StoreCreate, StoreRead, StoreUpdate

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
