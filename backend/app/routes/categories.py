"""Category management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, status
from psycopg.errors import UniqueViolation

from app.deps import ManagerStore, Store
from app.errors import ConflictError, NotFoundError
from app.models import category as category_model
from app.schemas.product import CategoryCreate, CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(context: Store) -> list[dict]:
    """Categories with the number of active products in each."""
    return category_model.list_categories(context.store_id)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, context: ManagerStore) -> dict:
    try:
        created = category_model.create(context.store_id, payload.name, payload.description)
    except UniqueViolation as exc:
        raise ConflictError(f"Category '{payload.name}' already exists") from exc
    return {**created, "product_count": 0}


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryCreate, context: ManagerStore) -> dict:
    existing = category_model.get(category_id, context.store_id)
    if existing is None:
        raise NotFoundError(f"Category {category_id} not found")
    try:
        updated = category_model.rename(
            category_id, context.store_id, payload.name, payload.description
        )
    except UniqueViolation as exc:
        raise ConflictError(f"Category '{payload.name}' already exists") from exc
    return {
        **updated,
        "product_count": category_model.product_count(context.store_id, updated["name"]),
    }


@router.delete("/{category_id}")
def delete_category(category_id: int, context: ManagerStore) -> dict:
    """Remove an empty category. Categories in use cannot be deleted."""
    existing = category_model.get(category_id, context.store_id)
    if existing is None:
        raise NotFoundError(f"Category {category_id} not found")

    in_use = category_model.product_count(context.store_id, existing["name"])
    if in_use:
        raise ConflictError(
            f"{in_use} product(s) still use '{existing['name']}'. Move them first."
        )

    category_model.delete(category_id, context.store_id)
    return {"status": "deleted"}
