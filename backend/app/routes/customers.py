"""Customer endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from psycopg.errors import UniqueViolation

from app.deps import ManagerStore, Store
from app.errors import ConflictError, NotFoundError
from app.models import customer as customer_model
from app.models import sale as sale_model
from app.schemas.business import (
    CustomerCreate,
    CustomerDetail,
    CustomerOut,
    CustomerPage,
    CustomerUpdate,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerPage)
def list_customers(
    context: Store,
    search: str | None = Query(default=None, description="Name, phone or email"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return {
        "items": customer_model.list_customers(context.store_id, search, limit, offset),
        "total": customer_model.count_customers(context.store_id, search),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, context: Store) -> dict:
    """Contact details plus purchase history and averages."""
    customer = customer_model.get(customer_id, context.store_id)
    if customer is None:
        raise NotFoundError(f"Customer {customer_id} not found")

    purchases = sale_model.list_sales(context.store_id, customer_id=customer_id, limit=50)
    count = int(customer["purchase_count"])
    return {
        **customer,
        "purchases": purchases,
        "average_order_value": (
            round(float(customer["total_spent"]) / count, 2) if count else 0
        ),
    }


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, context: Store) -> dict:
    data = payload.model_dump()
    data["email"] = str(data["email"]) if data["email"] else None
    try:
        created = customer_model.create(context.store_id, data)
    except UniqueViolation as exc:
        raise ConflictError(f"A customer with phone {payload.phone} already exists") from exc
    return {**created, "total_spent": 0, "purchase_count": 0, "last_purchase": None}


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerUpdate, context: Store) -> dict:
    if customer_model.get(customer_id, context.store_id) is None:
        raise NotFoundError(f"Customer {customer_id} not found")

    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"])
    try:
        return customer_model.update(customer_id, context.store_id, data)
    except UniqueViolation as exc:
        raise ConflictError("Another customer already uses that phone number") from exc


@router.delete("/{customer_id}")
def delete_customer(customer_id: int, context: ManagerStore) -> dict:
    """Remove a customer. Their invoices keep the name recorded at the till."""
    if customer_model.get(customer_id, context.store_id) is None:
        raise NotFoundError(f"Customer {customer_id} not found")
    customer_model.delete(customer_id, context.store_id)
    return {"status": "deleted"}
