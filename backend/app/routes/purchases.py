"""Purchase order endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.deps import ManagerStore, Store
from app.schemas.purchase import (
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderPage,
    PurchaseStatus,
    ReceiveRequest,
    ReorderSuggestions,
    ReorderToPurchase,
    StatusUpdate,
)
from app.services import purchase_service

router = APIRouter(prefix="/purchase-orders", tags=["purchases"])


@router.get("", response_model=PurchaseOrderPage)
def list_orders(
    context: Store,
    status: PurchaseStatus | None = Query(default=None),
    supplier_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return purchase_service.list_orders(context.store_id, status, supplier_id, limit, offset)


@router.get("/suggestions", response_model=ReorderSuggestions)
def reorder_suggestions(context: Store) -> dict:
    """Reorder recommendations grouped by supplier, ready to become orders."""
    return purchase_service.reorder_suggestions(context.store_id)


@router.post("/from-recommendations", response_model=PurchaseOrderDetail,
             status_code=status.HTTP_201_CREATED)
def create_from_recommendations(payload: ReorderToPurchase, context: ManagerStore) -> dict:
    """Turn the model's reorder advice into a draft purchase order."""
    return purchase_service.create_order_from_recommendations(
        context.store_id, payload.supplier_id, payload.product_ids, context.user_id
    )


@router.get("/{order_id}", response_model=PurchaseOrderDetail)
def get_order(order_id: int, context: Store) -> dict:
    return purchase_service.get_order(context.store_id, order_id)


@router.post("", response_model=PurchaseOrderDetail, status_code=status.HTTP_201_CREATED)
def create_order(payload: PurchaseOrderCreate, context: ManagerStore) -> dict:
    return purchase_service.create_order(
        context.store_id, payload.model_dump(mode="python"), context.user_id
    )


@router.patch("/{order_id}/status", response_model=PurchaseOrderDetail)
def set_status(order_id: int, payload: StatusUpdate, context: ManagerStore) -> dict:
    """Move an order along its lifecycle."""
    return purchase_service.set_status(context.store_id, order_id, payload.status)


@router.post("/{order_id}/receive", response_model=PurchaseOrderDetail)
def receive_order(order_id: int, payload: ReceiveRequest, context: ManagerStore) -> dict:
    """Book in a delivery: stock rises and the ledger records where it came from."""
    receipts = [item.model_dump() for item in payload.items] if payload.items else None
    return purchase_service.receive_order(
        context.store_id, order_id, receipts, context.user_id
    )
