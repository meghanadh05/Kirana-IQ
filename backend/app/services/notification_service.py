"""Generating and reading in-app notifications.

Alerts are derived from the same data the dashboard shows, not stored ahead of
time, so they cannot go stale. `refresh` is idempotent: running it twice updates
the same rows rather than producing a second copy of every warning.
"""

from __future__ import annotations

import logging
from typing import Any

from app.ml.predict import ModelNotTrainedError
from app.models import notification as notification_model
from app.models import product as product_model
from app.models import purchase as purchase_model
from app.services import analytics_service, inventory_service

logger = logging.getLogger(__name__)


def refresh(store_id: int) -> dict[str, Any]:
    """Regenerate stock, forecast and purchasing alerts for a store."""
    created = 0

    for row in product_model.list_products(store_id, stock_status="out", limit=50):
        notification_model.create(
            store_id,
            "STOCK",
            "CRITICAL",
            f"{row['name']} is out of stock",
            f"{row['sku']} has no units left. Sales of this product will be blocked.",
            link=f"/products/{row['id']}",
            dedupe_key=f"out-of-stock:{row['id']}",
        )
        created += 1

    try:
        for row in inventory_service.recommendations(store_id, risk_filter="CRITICAL")[:20]:
            cover = row["stock_cover_days"]
            when = f"{cover:.1f} days" if cover is not None else "an unknown time"
            notification_model.create(
                store_id,
                "CRITICAL",
                "CRITICAL",
                f"{row['name']} may run out soon",
                (
                    f"About {when} of stock left against a {row['lead_time_days']}-day "
                    f"lead time. Suggested order: {row['recommended_reorder_quantity']} units."
                ),
                link="/purchases/new",
                dedupe_key=f"critical-stock:{row['product_id']}",
            )
            created += 1

        for anomaly in analytics_service.detect_anomalies(store_id, limit=10):
            notification_model.create(
                store_id,
                "ANOMALY",
                "WARNING" if anomaly["severity"] == "HIGH" else "INFO",
                f"Unusual demand: {anomaly['name']}",
                anomaly["message"],
                link=f"/forecasting?product={anomaly['product_id']}",
                dedupe_key=f"anomaly:{anomaly['product_id']}",
            )
            created += 1
    except ModelNotTrainedError:
        logger.info("Store %s has no trained model; skipping forecast alerts", store_id)

    for order in purchase_model.list_orders(store_id, status="ORDERED", limit=20):
        notification_model.create(
            store_id,
            "PURCHASE",
            "INFO",
            f"{order['po_number']} is awaiting delivery",
            (
                f"{order['unit_count']} units from "
                f"{order['supplier_name'] or 'an unassigned supplier'}"
                + (f", expected {order['expected_delivery']}" if order["expected_delivery"] else "")
            ),
            link=f"/purchases/{order['id']}",
            dedupe_key=f"purchase-open:{order['id']}",
        )
        created += 1

    return {"refreshed": created, "unread": notification_model.unread_count(store_id)}
