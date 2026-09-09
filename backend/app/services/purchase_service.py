"""Purchasing: suppliers, purchase orders, receiving and reorder integration.

Receiving is the mirror image of checkout — stock arrives, the ledger records
where it came from, and the order's status follows the quantities actually
received. Like checkout, it is one transaction: a delivery that half-lands is
worse than one that does not land at all.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.database import transaction
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import inventory as inventory_model
from app.models import product as product_model
from app.models import purchase as purchase_model
from app.models import supplier as supplier_model
from app.services import forecast_service, inventory_service, store_service

logger = logging.getLogger(__name__)

STATUSES = ("DRAFT", "ORDERED", "PARTIALLY_RECEIVED", "RECEIVED", "CANCELLED")

# Which status a purchase order may move to from where. Receiving is handled
# separately because the resulting status depends on the quantities.
ALLOWED_TRANSITIONS = {
    "DRAFT": {"ORDERED", "CANCELLED"},
    "ORDERED": {"PARTIALLY_RECEIVED", "RECEIVED", "CANCELLED"},
    "PARTIALLY_RECEIVED": {"RECEIVED", "CANCELLED"},
    "RECEIVED": set(),
    "CANCELLED": set(),
}

ZERO = Decimal("0.00")


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------
# Suppliers
# --------------------------------------------------------------------------


def list_suppliers(store_id: int, search: str | None, include_inactive: bool) -> list[dict[str, Any]]:
    return supplier_model.list_suppliers(store_id, search, include_inactive)


def get_supplier(store_id: int, supplier_id: int) -> dict[str, Any]:
    supplier = supplier_model.get(supplier_id, store_id)
    if supplier is None:
        raise NotFoundError(f"Supplier {supplier_id} not found")

    totals = purchase_model.supplier_totals(supplier_id, store_id) or {}
    return {
        **supplier,
        "products": supplier_model.supplied_products(supplier_id, store_id),
        "purchase_orders": purchase_model.history_for_supplier(supplier_id, store_id),
        "order_count": int(totals.get("order_count", 0)),
        "open_orders": int(totals.get("open_orders", 0)),
        "total_purchased": round(float(totals.get("total_purchased", 0)), 2),
    }


def create_supplier(store_id: int, data: dict[str, Any]) -> dict[str, Any]:
    supplier = supplier_model.create(store_id, data)
    return {**supplier, "product_count": 0, "open_orders": 0, "total_purchased": 0}


def update_supplier(store_id: int, supplier_id: int, data: dict[str, Any]) -> dict[str, Any]:
    if supplier_model.get(supplier_id, store_id) is None:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    return supplier_model.update(supplier_id, store_id, data)


def archive_supplier(store_id: int, supplier_id: int) -> dict[str, Any]:
    if supplier_model.get(supplier_id, store_id) is None:
        raise NotFoundError(f"Supplier {supplier_id} not found")
    supplier_model.archive(supplier_id, store_id)
    return supplier_model.get(supplier_id, store_id)


# --------------------------------------------------------------------------
# Purchase orders
# --------------------------------------------------------------------------


def create_order(store_id: int, payload: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Create a purchase order. Line costs default to each product's cost price."""
    items = payload.get("items") or []
    if not items:
        raise ValidationError("A purchase order needs at least one line")

    supplier_id = payload.get("supplier_id")
    if supplier_id is not None and supplier_model.get(supplier_id, store_id) is None:
        raise NotFoundError(f"Supplier {supplier_id} not found")

    status = payload.get("status") or "DRAFT"
    if status not in ("DRAFT", "ORDERED"):
        raise ValidationError("A new purchase order must be DRAFT or ORDERED")

    settings = store_service.get_settings_for_store(store_id)
    prefix = settings["purchase_order_prefix"] if settings else "PO"

    lines = _build_order_lines(store_id, items)
    subtotal = sum((line["line_total"] for line in lines), ZERO)
    tax = sum(
        (_money(line["line_total"] * line["tax_rate"] / Decimal("100")) for line in lines), ZERO
    )

    with transaction() as conn:
        po_number = purchase_model.next_po_number(conn, store_id, prefix)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO purchase_orders (store_id, po_number, supplier_id, status,
                                             subtotal, tax, total, expected_delivery,
                                             notes, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    store_id, po_number, supplier_id, status, subtotal, tax,
                    _money(subtotal + tax), payload.get("expected_delivery"),
                    payload.get("notes"), user_id,
                ),
            )
            order_id = int(cur.fetchone()["id"])

            for line in lines:
                cur.execute(
                    """
                    INSERT INTO purchase_order_items (purchase_order_id, store_id, product_id,
                                                      quantity, cost_price, tax_rate, line_total)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id, store_id, line["product_id"], line["quantity"],
                        line["cost_price"], line["tax_rate"], line["line_total"],
                    ),
                )

    return get_order(store_id, order_id)


def _build_order_lines(store_id: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}

    for item in items:
        product_id = int(item["product_id"])
        quantity = int(item["quantity"])
        if quantity <= 0:
            raise ValidationError("Purchase quantities must be at least 1")

        product = product_model.get_product(product_id, store_id)
        if product is None:
            raise NotFoundError(f"Product {product_id} is not in this store")

        cost = _money(
            item["cost_price"] if item.get("cost_price") is not None else product["cost_price"]
        )
        if product_id in merged:
            merged[product_id]["quantity"] += quantity
        else:
            merged[product_id] = {
                "product_id": product_id,
                "quantity": quantity,
                "cost_price": cost,
                "tax_rate": _money(product["tax_rate"]),
            }

    for line in merged.values():
        line["line_total"] = _money(line["cost_price"] * line["quantity"])
    return list(merged.values())


def get_order(store_id: int, order_id: int) -> dict[str, Any]:
    order = purchase_model.get(order_id, store_id)
    if order is None:
        raise NotFoundError(f"Purchase order {order_id} not found")

    items = purchase_model.get_items(order_id, store_id)
    return {
        **order,
        "items": items,
        "item_count": len(items),
        "unit_count": sum(int(item["quantity"]) for item in items),
        "received_count": sum(int(item["received_quantity"]) for item in items),
    }


def list_orders(
    store_id: int, status: str | None, supplier_id: int | None, limit: int, offset: int
) -> dict[str, Any]:
    return {
        "items": purchase_model.list_orders(store_id, status, supplier_id, limit, offset),
        "total": purchase_model.count_orders(store_id, status, supplier_id),
        "limit": limit,
        "offset": offset,
    }


def set_status(store_id: int, order_id: int, status: str) -> dict[str, Any]:
    """Move an order along its lifecycle, refusing transitions that make no sense."""
    order = purchase_model.get(order_id, store_id)
    if order is None:
        raise NotFoundError(f"Purchase order {order_id} not found")
    if status not in STATUSES:
        raise ValidationError(f"status must be one of {list(STATUSES)}")
    if status not in ALLOWED_TRANSITIONS[order["status"]]:
        raise ConflictError(
            f"{order['po_number']} is {order['status']} and cannot become {status}"
        )

    with transaction() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE purchase_orders SET status = %s, updated_at = NOW() "
            "WHERE id = %s AND store_id = %s",
            (status, order_id, store_id),
        )
    return get_order(store_id, order_id)


def receive_order(
    store_id: int, order_id: int, receipts: list[dict[str, Any]] | None, user_id: int
) -> dict[str, Any]:
    """Book in a delivery: stock rises, the ledger records the source, status follows.

    Omitting `receipts` receives everything still outstanding, which is the
    common case — the delivery matched the order.
    """
    order = purchase_model.get(order_id, store_id)
    if order is None:
        raise NotFoundError(f"Purchase order {order_id} not found")
    if order["status"] == "CANCELLED":
        raise ConflictError(f"{order['po_number']} was cancelled and cannot be received")
    if order["status"] == "RECEIVED":
        raise ConflictError(f"{order['po_number']} has already been fully received")
    if order["status"] == "DRAFT":
        raise ConflictError(
            f"{order['po_number']} is still a draft. Mark it as ordered before receiving."
        )

    items = {int(item["id"]): item for item in purchase_model.get_items(order_id, store_id)}
    if not items:
        raise ValidationError("This purchase order has no lines to receive")

    requested = _receipt_quantities(items, receipts)
    if not any(requested.values()):
        raise ValidationError("Nothing left to receive on this order")

    with transaction() as conn:
        for item_id, quantity in requested.items():
            if quantity <= 0:
                continue
            item = items[item_id]

            inventory_model.apply_movement(
                conn,
                store_id=store_id,
                product_id=int(item["product_id"]),
                quantity_change=quantity,
                transaction_type="PURCHASE",
                reference_type="PURCHASE_ORDER",
                reference_id=order_id,
                notes=f"Received on {order['po_number']}",
                created_by=user_id,
            )

            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE purchase_order_items SET received_quantity = received_quantity + %s "
                    "WHERE id = %s AND store_id = %s",
                    (quantity, item_id, store_id),
                )
                # A delivery is also the freshest evidence of what this product
                # costs, so the catalogue cost price follows it.
                cur.execute(
                    "UPDATE products SET cost_price = %s, updated_at = NOW() "
                    "WHERE id = %s AND store_id = %s",
                    (item["cost_price"], item["product_id"], store_id),
                )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT SUM(quantity) AS ordered, SUM(received_quantity) AS received
                FROM purchase_order_items WHERE purchase_order_id = %s
                """,
                (order_id,),
            )
            totals = cur.fetchone()
            fully_received = int(totals["received"]) >= int(totals["ordered"])
            cur.execute(
                "UPDATE purchase_orders SET status = %s, updated_at = NOW(), "
                "received_at = CASE WHEN %s THEN NOW() ELSE received_at END "
                "WHERE id = %s AND store_id = %s",
                (
                    "RECEIVED" if fully_received else "PARTIALLY_RECEIVED",
                    fully_received,
                    order_id,
                    store_id,
                ),
            )

    forecast_service.clear_cache()
    return get_order(store_id, order_id)


def _receipt_quantities(
    items: dict[int, dict[str, Any]], receipts: list[dict[str, Any]] | None
) -> dict[int, int]:
    """How much of each line to book in, defaulting to everything outstanding."""
    if not receipts:
        return {
            item_id: int(item["quantity"]) - int(item["received_quantity"])
            for item_id, item in items.items()
        }

    quantities: dict[int, int] = {}
    for receipt in receipts:
        item_id = int(receipt["item_id"])
        if item_id not in items:
            raise NotFoundError(f"Line {item_id} is not on this purchase order")

        quantity = int(receipt["quantity"])
        if quantity < 0:
            raise ValidationError("Received quantity cannot be negative")

        outstanding = int(items[item_id]["quantity"]) - int(items[item_id]["received_quantity"])
        if quantity > outstanding:
            raise ValidationError(
                f"{items[item_id]['product_name']}: {outstanding} outstanding, "
                f"{quantity} received"
            )
        quantities[item_id] = quantity
    return quantities


# --------------------------------------------------------------------------
# Reorder recommendations → purchase orders
# --------------------------------------------------------------------------


def reorder_suggestions(store_id: int, risk_levels: tuple[str, ...] = ("CRITICAL", "HIGH")) -> dict[str, Any]:
    """Group the model's reorder recommendations by supplier.

    This is what turns "reorder 95 units" into something a shop owner can act
    on: one order per supplier, not one decision per product.
    """
    recommendations = [
        row
        for row in inventory_service.recommendations(store_id)
        if row["risk"] in risk_levels and row["recommended_reorder_quantity"] > 0
    ]

    suppliers = {s["id"]: s for s in supplier_model.list_suppliers(store_id)}
    grouped: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for row in recommendations:
        grouped[row.get("supplier_id")].append(row)

    groups = []
    for supplier_id, rows in grouped.items():
        supplier = suppliers.get(supplier_id) if supplier_id else None
        lead_time = (
            int(supplier["default_lead_time_days"])
            if supplier
            else max((int(row["lead_time_days"]) for row in rows), default=3)
        )
        groups.append(
            {
                "supplier_id": supplier_id,
                "supplier_name": supplier["name"] if supplier else None,
                "expected_delivery": (date.today() + timedelta(days=lead_time)).isoformat(),
                "product_count": len(rows),
                "total_units": sum(row["recommended_reorder_quantity"] for row in rows),
                "estimated_cost": round(sum(row["estimated_cost"] for row in rows), 2),
                "items": rows,
            }
        )

    # Unassigned products last: they need a supplier chosen before ordering.
    groups.sort(key=lambda group: (group["supplier_id"] is None, -group["estimated_cost"]))
    return {"groups": groups, "total_products": len(recommendations)}


def create_order_from_recommendations(
    store_id: int, supplier_id: int | None, product_ids: list[int] | None, user_id: int
) -> dict[str, Any]:
    """Turn recommendations into a draft purchase order, ready to review and send."""
    recommendations = {
        row["product_id"]: row
        for row in inventory_service.recommendations(store_id)
        if row["recommended_reorder_quantity"] > 0
    }

    if product_ids:
        chosen = [recommendations[pid] for pid in product_ids if pid in recommendations]
        missing = [pid for pid in product_ids if pid not in recommendations]
        if missing:
            raise ValidationError(
                f"No reorder is recommended for product(s) {missing}. "
                "They have enough stock, or not enough history to forecast."
            )
    else:
        chosen = [
            row
            for row in recommendations.values()
            if row.get("supplier_id") == supplier_id and row["risk"] in ("CRITICAL", "HIGH")
        ]

    if not chosen:
        raise ValidationError("Nothing to reorder for this selection")

    expected = None
    if supplier_id:
        supplier = supplier_model.get(supplier_id, store_id)
        if supplier is None:
            raise NotFoundError(f"Supplier {supplier_id} not found")
        expected = date.today() + timedelta(days=int(supplier["default_lead_time_days"]))

    return create_order(
        store_id,
        {
            "supplier_id": supplier_id,
            "status": "DRAFT",
            "expected_delivery": expected,
            "notes": "Created from Kirana-IQ reorder recommendations",
            "items": [
                {
                    "product_id": row["product_id"],
                    "quantity": row["recommended_reorder_quantity"],
                    "cost_price": row["cost_price"],
                }
                for row in chosen
            ],
        },
        user_id,
    )
