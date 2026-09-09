"""Inventory intelligence endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.ml.predict import InsufficientHistoryError, ModelNotTrainedError
from app.schemas.inventory import InventoryRecommendation, InventorySummary
from app.services import inventory_service

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/recommendations", response_model=list[InventoryRecommendation])
def get_recommendations(
    risk: str | None = Query(default=None, description="Filter to one risk level"),
) -> list[dict]:
    """Reorder recommendations for the whole catalogue, most urgent first."""
    if risk is not None and risk not in inventory_service.RISK_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"risk must be one of {list(inventory_service.RISK_LEVELS)}",
        )

    try:
        return inventory_service.recommendations(risk_filter=risk)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/summary", response_model=InventorySummary)
def get_summary() -> dict:
    """Headline inventory counts for the dashboard cards."""
    try:
        return inventory_service.summarise(inventory_service.recommendations())
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{product_id}", response_model=InventoryRecommendation)
def get_product_recommendation(product_id: int) -> dict:
    """Inventory assessment for a single product."""
    try:
        result = inventory_service.analyse_product(product_id)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InsufficientHistoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return result
