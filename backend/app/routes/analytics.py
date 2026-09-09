"""Analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.ml.predict import ModelNotTrainedError
from app.schemas.analytics import (
    AnalyticsOverview,
    Anomaly,
    CategoryTrend,
    DemandTrend,
    ProductMover,
)
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def get_overview(
    anomaly_limit: int = Query(default=5, ge=1, le=50),
) -> dict:
    """Everything the dashboard landing page needs, in one request."""
    try:
        return analytics_service.overview(anomaly_limit=anomaly_limit)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/demand-trend", response_model=DemandTrend)
def get_demand_trend(
    history_days: int = Query(default=30, ge=7, le=180),
    forecast_days: int = Query(default=7, ge=1, le=30),
) -> dict:
    """Catalogue-wide daily demand: recent actuals followed by the forecast."""
    try:
        return analytics_service.demand_trend(history_days, forecast_days)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/anomalies", response_model=list[Anomaly])
def get_anomalies(
    limit: int | None = Query(default=None, ge=1, le=100),
) -> list[dict]:
    """Products whose recent demand deviates from their own recent baseline."""
    return analytics_service.detect_anomalies(limit=limit)


@router.get("/top-products", response_model=list[ProductMover])
def get_top_products(
    days: int = Query(default=30, ge=7, le=365),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    """Best sellers by units over the trailing window."""
    return analytics_service.top_products(days=days, limit=limit)


@router.get("/slow-moving", response_model=list[ProductMover])
def get_slow_moving(
    days: int = Query(default=30, ge=7, le=365),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[dict]:
    """Products selling well below the catalogue average — candidate dead stock."""
    return analytics_service.slow_moving(days=days, limit=limit)


@router.get("/category-trends", response_model=list[CategoryTrend])
def get_category_trends(
    days: int = Query(default=30, ge=7, le=180),
) -> list[dict]:
    """Category demand for the trailing window versus the window before it."""
    return analytics_service.category_trends(days=days)
