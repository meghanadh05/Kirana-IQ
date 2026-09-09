"""Inventory: on-hand stock, the movement ledger, adjustments and reorder advice."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.deps import ManagerStore, Store
from app.errors import ModelUnavailableError, NotFoundError, ValidationError
from app.ml.predict import InsufficientHistoryError, ModelNotTrainedError
from app.models import inventory as inventory_model
from app.schemas.inventory import (
    AdjustmentCreate,
    InventoryRecommendation,
    InventorySummary,
    MovementOut,
    MovementPage,
    StockPosition,
    TransactionType,
)
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("", response_model=StockPosition)
def get_stock_position(
    context: Store,
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    """Current stock for every active product, plus store-wide valuation."""
    return inventory_service.stock_position(context.store_id, limit=limit)


@router.get("/movements", response_model=MovementPage)
def list_movements(
    context: Store,
    product_id: int | None = Query(default=None, gt=0),
    type: TransactionType | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """The stock ledger: every movement, newest first."""
    return {
        "items": inventory_model.list_movements(
            context.store_id, product_id=product_id, transaction_type=type,
            limit=limit, offset=offset,
        ),
        "total": inventory_model.count_movements(
            context.store_id, product_id=product_id, transaction_type=type
        ),
        "limit": limit,
        "offset": offset,
    }


@router.post("/adjustments", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def create_adjustment(payload: AdjustmentCreate, context: ManagerStore) -> dict:
    """Correct stock for damage, expiry, loss or a physical count."""
    return inventory_service.adjust_stock(
        store_id=context.store_id,
        product_id=payload.product_id,
        quantity_change=payload.quantity_change,
        reason=payload.reason,
        notes=payload.notes,
        user_id=context.user_id,
    )


@router.get("/recommendations", response_model=list[InventoryRecommendation])
def get_recommendations(
    context: Store,
    risk: str | None = Query(default=None, description="Filter to one risk level"),
) -> list[dict]:
    """Reorder recommendations for the whole catalogue, most urgent first."""
    if risk is not None and risk not in inventory_service.RISK_LEVELS:
        raise ValidationError(f"risk must be one of {list(inventory_service.RISK_LEVELS)}")

    try:
        return inventory_service.recommendations(context.store_id, risk_filter=risk)
    except ModelNotTrainedError as exc:
        raise ModelUnavailableError(str(exc)) from exc


@router.get("/summary", response_model=InventorySummary)
def get_summary(context: Store) -> dict:
    """Headline inventory counts for the dashboard cards."""
    try:
        return inventory_service.summarise(inventory_service.recommendations(context.store_id))
    except ModelNotTrainedError as exc:
        raise ModelUnavailableError(str(exc)) from exc


@router.get("/{product_id}", response_model=InventoryRecommendation)
def get_product_recommendation(product_id: int, context: Store) -> dict:
    """Inventory assessment for a single product."""
    try:
        result = inventory_service.analyse_product(product_id, context.store_id)
    except ModelNotTrainedError as exc:
        raise ModelUnavailableError(str(exc)) from exc
    except InsufficientHistoryError as exc:
        raise ValidationError(str(exc)) from exc

    if result is None:
        raise NotFoundError(f"Product {product_id} not found")
    return result
