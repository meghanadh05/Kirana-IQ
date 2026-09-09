"""Forecasting and training endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.ml.predict import InsufficientHistoryError, ModelNotTrainedError
from app.schemas.forecast import ForecastWithHistory, TrainingStatus
from app.services import forecast_service

router = APIRouter(tags=["forecast"])

SUPPORTED_DAYS = (7, 14, 30)


@router.get("/forecast/{product_id}", response_model=ForecastWithHistory)
def get_forecast(
    product_id: int,
    days: int = Query(default=7, description="Forecast horizon: 7, 14 or 30 days"),
    history_days: int = Query(default=60, ge=0, le=365),
) -> dict:
    """Predicted daily demand for one product, with recent history for context."""
    if days not in SUPPORTED_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"days must be one of {list(SUPPORTED_DAYS)}, got {days}",
        )

    try:
        result = forecast_service.forecast_by_id(product_id, days=days)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InsufficientHistoryError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not result:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    result["history"] = forecast_service.history_series(product_id, days=history_days)
    return result


@router.get("/model", response_model=TrainingStatus)
def get_model_status() -> dict:
    """Which model is serving forecasts, and how it scored."""
    return forecast_service.training_status()


@router.post("/train")
def train_model() -> dict:
    """Retrain on current database contents and reload the serving model.

    Synchronous and takes a few seconds on the sample dataset — acceptable for
    an operation a shop owner runs occasionally, not per request.
    """
    try:
        report = forecast_service.retrain()
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "status": "trained",
        "selected_model": report["selected_model"],
        "trained_at": report["trained_at"],
        "rows": report["rows"],
        "date_ranges": report["date_ranges"],
        "test_scores": report["test_scores"],
        "wape_improvement_over_baseline_pct": round(
            report["wape_improvement_over_baseline_pct"], 2
        ),
    }
