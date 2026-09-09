"""Pydantic request/response models for products and categories."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Unit = Literal["piece", "kg", "gram", "litre", "ml", "packet", "box"]
StockStatus = Literal["in", "low", "out"]


class ProductCreate(BaseModel):
    """Payload for POST /products."""

    sku: str = Field(min_length=1, max_length=50, description="Unique stock keeping unit code")
    barcode: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: str = Field(min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    unit: Unit = "piece"
    selling_price: Decimal = Field(ge=0, le=10_000_000, decimal_places=2)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, le=10_000_000, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, decimal_places=2)
    current_stock: int = Field(default=0, ge=0, le=10_000_000, description="Opening stock")
    reorder_level: int = Field(default=0, ge=0, le=10_000_000)
    lead_time_days: int = Field(default=3, ge=0, le=365, description="Supplier delivery time")
    supplier_id: int | None = Field(default=None, gt=0)
    is_active: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sku": "DRY-001",
                "barcode": "8901234567890",
                "name": "Amul Taaza Milk 1L",
                "category": "Dairy",
                "brand": "Amul",
                "unit": "piece",
                "selling_price": "33.00",
                "cost_price": "27.50",
                "tax_rate": "5.00",
                "current_stock": 120,
                "reorder_level": 60,
                "lead_time_days": 2,
            }
        }
    )


class ProductUpdate(BaseModel):
    """Payload for PATCH /products/{id}. Stock is not editable here."""

    sku: str | None = Field(default=None, min_length=1, max_length=50)
    barcode: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    unit: Unit | None = None
    selling_price: Decimal | None = Field(default=None, ge=0, le=10_000_000, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, le=10_000_000, decimal_places=2)
    tax_rate: Decimal | None = Field(default=None, ge=0, le=100, decimal_places=2)
    reorder_level: int | None = Field(default=None, ge=0, le=10_000_000)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    supplier_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ProductOut(BaseModel):
    """A product as returned by the API."""

    id: int
    store_id: int
    sku: str
    barcode: str | None = None
    name: str
    description: str | None = None
    category: str
    brand: str | None = None
    unit: str
    selling_price: Decimal
    cost_price: Decimal
    tax_rate: Decimal
    current_stock: int
    reorder_level: int
    lead_time_days: int
    supplier_id: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    """A page of products plus the total, so the client can paginate."""

    items: list[ProductOut]
    total: int
    limit: int
    offset: int


class CatalogueStats(BaseModel):
    total: int
    out_of_stock: int
    low_stock: int
    inventory_cost_value: Decimal
    inventory_retail_value: Decimal


class CategoryOut(BaseModel):
    id: int
    store_id: int
    name: str
    description: str | None = None
    product_count: int = 0
    created_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ImportResult(BaseModel):
    created: int
    updated: int
    failed: int
    errors: list[dict]
