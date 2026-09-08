"""Pydantic request/response models for products."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    """Payload for POST /products."""

    sku: str = Field(min_length=1, max_length=50, description="Unique stock keeping unit code")
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    unit_price: Decimal = Field(ge=0, decimal_places=2, description="Selling price per unit")
    current_stock: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=0, ge=0)
    lead_time_days: int = Field(default=1, ge=0, le=365, description="Supplier delivery time")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sku": "DRY-001",
                "name": "Amul Taaza Milk 1L",
                "category": "Dairy",
                "unit_price": "33.00",
                "current_stock": 120,
                "reorder_level": 60,
                "lead_time_days": 2,
            }
        }
    )


class ProductOut(BaseModel):
    """A product as returned by the API."""

    id: int
    sku: str
    name: str
    category: str
    unit_price: Decimal
    current_stock: int
    reorder_level: int
    lead_time_days: int
