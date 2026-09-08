"""Pydantic request/response models for sales."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SaleCreate(BaseModel):
    """Payload for POST /sales."""

    product_id: int = Field(gt=0)
    quantity: int = Field(ge=0, le=1_000_000)
    sale_date: date
    unit_price: Decimal = Field(ge=0, decimal_places=2)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": 1,
                "quantity": 12,
                "sale_date": "2026-09-08",
                "unit_price": "33.00",
            }
        }
    )


class SaleOut(BaseModel):
    """A sale as returned by the API."""

    id: int
    product_id: int
    quantity: int
    sale_date: date
    unit_price: Decimal
