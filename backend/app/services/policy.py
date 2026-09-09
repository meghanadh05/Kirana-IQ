"""Per-store inventory and anomaly policy.

The thresholds that decide "is this critical?" belong to a shop, not to a
deployment: a bakery restocking daily and a wholesaler restocking monthly want
different answers. Environment variables remain the defaults a new store starts
from; `store_settings` is what actually applies.

The returned object exposes the same attribute names as `Settings`, so the
existing inventory and anomaly functions accept either.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class StorePolicy:
    critical_cover_days: float
    medium_cover_buffer_days: float
    overstock_cover_days: float
    safety_days: int
    service_level_z: float
    low_stock_threshold: int
    anomaly_recent_days: int
    anomaly_baseline_days: int
    anomaly_min_change: float
    anomaly_min_zscore: float
    slow_moving_threshold: float


def for_store(store_id: int) -> StorePolicy:
    """Resolve a store's effective policy, falling back to global defaults."""
    from app.services import store_service

    settings = get_settings()
    row = store_service.get_settings_for_store(store_id) or {}

    def value(key: str, default):
        raw = row.get(key)
        return default if raw is None else type(default)(raw)

    return StorePolicy(
        critical_cover_days=value("critical_cover_days", settings.critical_cover_days),
        medium_cover_buffer_days=value(
            "medium_cover_buffer_days", settings.medium_cover_buffer_days
        ),
        overstock_cover_days=value("overstock_cover_days", settings.overstock_cover_days),
        safety_days=value("safety_days", settings.safety_days),
        service_level_z=value("service_level_z", settings.service_level_z),
        low_stock_threshold=value("low_stock_threshold", 10),
        # Anomaly tuning stays global for now: it is a statistical sensitivity
        # dial, not a business decision a shop owner has an opinion about.
        anomaly_recent_days=settings.anomaly_recent_days,
        anomaly_baseline_days=settings.anomaly_baseline_days,
        anomaly_min_change=settings.anomaly_min_change,
        anomaly_min_zscore=settings.anomaly_min_zscore,
        slow_moving_threshold=settings.slow_moving_threshold,
    )
