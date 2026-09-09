"""Response models for forecasting endpoints."""

from __future__ import annotations

from datetime import date, datetime

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


class ForecastRunOut(BaseModel):
    id: int
    status: str
    model_name: str | None = None
    rows_used: int | None = None
    products: int | None = None
    metrics: dict | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class TrainingStatus(BaseModel):
    """What the Forecasting screen shows above the Retrain button."""

    trained: bool
    model_name: str | None = None
    trained_at: str | None = None
    features: int | None = None
    metrics: dict | None = None
    store_specific: bool = False
    training_rows: int | None = None
    training_days: int | None = None
    products: int | None = None
    history_days: int = 0
    last_run: ForecastRunOut | None = None


class TrainingReport(BaseModel):
    status: str
    selected_model: str
    trained_at: str
    rows: dict
    products: int
    training_days: int
    date_ranges: dict
    test_scores: dict
    wape_improvement_over_baseline_pct: float
