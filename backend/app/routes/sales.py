"""Sales endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.models import product as product_model
from app.models import sale as sale_model
from app.schemas.sale import SaleCreate, SaleOut

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate) -> dict:
    """Record a sale against an existing product."""
    if product_model.get_product(payload.product_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Product {payload.product_id} not found"
        )
    return sale_model.create_sale(payload.model_dump())


@router.get("/{product_id}", response_model=list[SaleOut])
def list_sales(
    product_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> list[dict]:
    """Sales history for one product, oldest first."""
    if product_model.get_product(product_id) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    return sale_model.list_sales(product_id, start_date, end_date, limit)


@router.get("/{product_id}/summary")
def sales_summary(product_id: int) -> dict:
    """Record count, total units and date span for one product."""
    if product_model.get_product(product_id) is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return sale_model.sales_summary(product_id)
