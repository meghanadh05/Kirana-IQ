"""Dashboard, command centre and business analytics endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.deps import Store
from app.schemas.business import Period
from app.services import business_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(context: Store) -> dict:
    """Everything the overview screen needs, in one request."""
    return business_service.dashboard(context.store_id)


@router.get("/briefing")
def get_briefing(context: Store) -> dict:
    """What needs attention today, and the actions that follow from it."""
    return business_service.briefing(context.store_id, context.user["full_name"])


analytics = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics.get("/sales")
def sales_analytics(
    context: Store,
    period: Period = Query(default="30d"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> dict:
    """Revenue, orders, average order value and payment split over a period."""
    start, end = business_service.resolve_period(period, start_date, end_date)
    return business_service.sales_analytics(context.store_id, start, end)


@analytics.get("/products")
def product_analytics(
    context: Store,
    period: Period = Query(default="30d"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """Best sellers, most profitable products, worst sellers and non-movers."""
    start, end = business_service.resolve_period(period, start_date, end_date)
    return business_service.product_analytics(context.store_id, start, end, limit)


@analytics.get("/inventory")
def inventory_analytics(
    context: Store,
    period: Period = Query(default="30d"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> dict:
    """Valuation, stock turnover, dead stock and overstock."""
    start, end = business_service.resolve_period(period, start_date, end_date)
    return business_service.inventory_analytics(context.store_id, start, end)


@analytics.get("/categories")
def category_analytics(
    context: Store,
    days: int = Query(default=30, ge=7, le=365),
) -> list[dict]:
    """Category sales, growth against the previous window, and contribution."""
    return business_service.category_analytics(context.store_id, days)


@analytics.get("/profit")
def profit_analytics(
    context: Store,
    period: Period = Query(default="30d"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
) -> dict:
    """Gross profit from sales, and an estimate of operating profit after expenses."""
    start, end = business_service.resolve_period(period, start_date, end_date)
    return business_service.profit_summary(context.store_id, start, end)
