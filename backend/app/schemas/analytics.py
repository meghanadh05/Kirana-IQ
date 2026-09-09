"""Response models for analytics endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.inventory import InventoryRecommendation


class Anomaly(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    direction: Literal["SPIKE", "DROP"]
    severity: Literal["MEDIUM", "HIGH"]
    recent_daily_average: float
    baseline_daily_average: float
    change_pct: float | None = Field(
        default=None, description="None when the baseline window sold nothing"
    )
    z_score: float | None
    recent_days: int
    baseline_days: int
    message: str


class ProductMover(BaseModel):
    product_id: int
    sku: str
    name: str
    category: str
    total_units: int
    total_revenue: float
    daily_average: float
    current_stock: int


class CategoryTrend(BaseModel):
    category: str
    current_units: int
    previous_units: int
    change_pct: float | None
    direction: Literal["UP", "DOWN", "FLAT"]
    daily_average: float


class DemandTrendPoint(BaseModel):
    date: str
    quantity: int | None = None
    predicted_demand: int | None = None


class DemandTrend(BaseModel):
    history: list[DemandTrendPoint]
    forecast: list[DemandTrendPoint]


class AnalyticsOverview(BaseModel):
    total_products: int
    critical_products: int
    high_risk_products: int
    medium_risk_products: int
    low_risk_products: int
    overstocked_products: int
    expected_7_day_units: float
    total_reorder_units: int
    anomaly_count: int
    anomalies: list[Anomaly]
    top_reorders: list[InventoryRecommendation]
