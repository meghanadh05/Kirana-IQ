"""Response models for inventory endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class InventoryRecommendation(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
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
