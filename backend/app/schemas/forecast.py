"""Response models for forecasting endpoints."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    date: date
    predicted_demand: int = Field(ge=0, description="Predicted units, never negative")


class ForecastResponse(BaseModel):
    product_id: int
    sku: str
    name: str
    forecast_days: int
    total_predicted_demand: int
    forecast: list[ForecastPoint]


class HistoryPoint(BaseModel):
    date: date
    quantity: int


class ForecastWithHistory(ForecastResponse):
    """Forecast plus recent observed demand, for the chart on the forecast page."""

    history: list[HistoryPoint]


class TrainingStatus(BaseModel):
    trained: bool
    model_name: str | None = None
    trained_at: str | None = None
    features: int | None = None
    metrics: dict | None = None
