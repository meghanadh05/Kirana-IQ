"""Supplier endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.deps import ManagerStore, Store
from app.schemas.purchase import (
    SupplierCreate,
    SupplierDetail,
    SupplierOut,
    SupplierUpdate,
)
from app.services import purchase_service

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("", response_model=list[SupplierOut])
def list_suppliers(
    context: Store,
    search: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
) -> list[dict]:
    return purchase_service.list_suppliers(context.store_id, search, include_inactive)


@router.get("/{supplier_id}", response_model=SupplierDetail)
def get_supplier(supplier_id: int, context: Store) -> dict:
    """Contact details, supplied products, purchase history and totals."""
    return purchase_service.get_supplier(context.store_id, supplier_id)


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, context: ManagerStore) -> dict:
    data = payload.model_dump()
    data["email"] = str(data["email"]) if data["email"] else None
    return purchase_service.create_supplier(context.store_id, data)


@router.patch("/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: int, payload: SupplierUpdate, context: ManagerStore) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    return purchase_service.update_supplier(context.store_id, supplier_id, data)


@router.delete("/{supplier_id}", response_model=SupplierOut)
def archive_supplier(supplier_id: int, context: ManagerStore) -> dict:
    """Archive a supplier. Purchase orders keep referencing it."""
    return purchase_service.archive_supplier(context.store_id, supplier_id)
