"""Response models for inventory endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
TransactionType = Literal[
    "SALE", "PURCHASE", "RETURN", "DAMAGE", "MANUAL_ADJUSTMENT", "OPENING_STOCK"
]
AdjustmentReason = Literal[
    "DAMAGE", "EXPIRED", "LOST", "COUNT_CORRECTION", "OPENING_STOCK", "RETURN", "OTHER"
]


class InventoryRecommendation(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    unit: str = "piece"
    supplier_id: int | None = None
    cost_price: float = 0
    current_stock: int
    reorder_level: int
    lead_time_days: int
    expected_7_day_demand: float
    average_daily_demand: float
    stock_cover_days: float | None = Field(
        default=None, description="None when no demand is predicted"
    )
    risk: RiskLevel
    overstock: bool
    demand_std_dev: float
    safety_stock: float
    target_stock: float
    recommended_reorder_quantity: int = Field(ge=0)
    estimated_cost: float = 0
    reason: str


class InventorySummary(BaseModel):
    total_products: int
    critical_products: int
    high_risk_products: int
    medium_risk_products: int
    low_risk_products: int
    overstocked_products: int
    expected_7_day_units: float
    total_reorder_units: int


class StockRow(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    unit: str
    current_stock: int
    reorder_level: int
    lead_time_days: int
    cost_price: float
    selling_price: float
    stock_value: float
    stock_status: Literal["OK", "LOW", "OUT_OF_STOCK"]
    last_movement_at: datetime | None = None


class StockPosition(BaseModel):
    """What is on the shelves right now. Available without a trained model."""

    products: list[StockRow]
    total_products: int
    out_of_stock: int
    low_stock: int
    inventory_cost_value: float
    inventory_retail_value: float


class MovementOut(BaseModel):
    id: int
    store_id: int
    product_id: int
    product_name: str | None = None
    sku: str | None = None
    type: TransactionType
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reference_type: str | None = None
    reference_id: int | None = None
    notes: str | None = None
    created_by: int | None = None
    created_by_name: str | None = None
    created_at: datetime


class MovementPage(BaseModel):
    items: list[MovementOut]
    total: int
    limit: int
    offset: int


class AdjustmentCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity_change: int = Field(
        description="Signed change: negative for damage or loss, positive for a correction up"
    )
    reason: AdjustmentReason
    notes: str | None = Field(default=None, max_length=500)
