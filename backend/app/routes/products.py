"""Product endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from psycopg.errors import UniqueViolation

from app.models import product as product_model
from app.schemas.product import ProductCreate, ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    category: str | None = Query(default=None, description="Exact category match"),
    search: str | None = Query(default=None, description="Substring match on name or SKU"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    """List products with optional category filter and search."""
    return product_model.list_products(
        category=category, search=search, limit=limit, offset=offset
    )


@router.get("/categories", response_model=list[str])
def list_categories() -> list[str]:
    """Distinct categories, for populating the dashboard filter."""
    return product_model.list_categories()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int) -> dict:
    """Fetch a single product by id."""
    product = product_model.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate) -> dict:
    """Create a product. SKUs must be unique."""
    try:
        return product_model.create_product(payload.model_dump())
    except UniqueViolation as exc:
        raise HTTPException(
            status_code=409, detail=f"SKU '{payload.sku}' already exists"
        ) from exc
