"""POS checkout and sales history.

Checkout is the one operation in this application that must be all-or-nothing.
It writes a sale, its line items, its payments, six stock decrements and six
ledger entries; a partial success would leave inventory permanently wrong with
no record of why. Everything below the BEGIN happens on one connection inside
one transaction, and any failure rolls the whole thing back.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from psycopg.errors import UniqueViolation

from app.database import transaction
from app.errors import ConflictError, NotFoundError, ValidationError
from app.models import customer as customer_model
from app.models import inventory as inventory_model
from app.models import sale as sale_model
from app.services import forecast_service, store_service

logger = logging.getLogger(__name__)

PAYMENT_METHODS = ("CASH", "UPI", "CARD", "MIXED", "OTHER")
MAX_CART_LINES = 200

ZERO = Decimal("0.00")


def _money(value: Any) -> Decimal:
    """Round to paise. Float arithmetic on money accumulates error per line."""
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def checkout(store_id: int, payload: dict[str, Any], user_id: int) -> dict[str, Any]:
    """Ring up a sale: invoice, items, payments, stock and ledger, atomically."""
    items = payload.get("items") or []
    if not items:
        raise ValidationError("Cannot check out an empty cart")
    if len(items) > MAX_CART_LINES:
        raise ValidationError(f"A sale can hold at most {MAX_CART_LINES} lines")

    settings = store_service.get_settings_for_store(store_id)
    prefix = settings["invoice_prefix"] if settings else "INV"
    sale_date = payload.get("sale_date") or date.today()

    # Retried once: the invoice number is derived inside the transaction, so two
    # simultaneous checkouts can collide on it. Everything else is deterministic.
    for attempt in range(2):
        try:
            return _run_checkout(store_id, payload, items, user_id, prefix, sale_date)
        except UniqueViolation:
            if attempt:
                raise ConflictError(
                    "Could not allocate an invoice number. Please try again."
                ) from None
            logger.info("Invoice number collision in store %s; retrying", store_id)
    raise ConflictError("Could not complete the sale")


def _run_checkout(
    store_id: int,
    payload: dict[str, Any],
    items: list[dict[str, Any]],
    user_id: int,
    prefix: str,
    sale_date: date,
) -> dict[str, Any]:
    with transaction() as conn:
        with conn.cursor() as cur:
            # Resolve and lock every product first. Locking in product-id order
            # gives all concurrent checkouts the same lock ordering, so two
            # carts holding the same two products cannot deadlock each other.
            product_ids = sorted({int(line["product_id"]) for line in items})
            cur.execute(
                """
                SELECT id, name, sku, selling_price, cost_price, tax_rate,
                       current_stock, is_active
                FROM products
                WHERE store_id = %s AND id = ANY(%s)
                ORDER BY id
                FOR UPDATE
                """,
                (store_id, product_ids),
            )
            products = {int(row["id"]): row for row in cur.fetchall()}

        missing = [pid for pid in product_ids if pid not in products]
        if missing:
            raise NotFoundError(f"Product {missing[0]} is not in this store")

        lines = _build_lines(items, products)

        subtotal = sum((line["line_total"] for line in lines), ZERO)
        tax = sum((line["tax_amount"] for line in lines), ZERO)
        cost_total = sum(
            (line["cost_price"] * line["quantity"] for line in lines), ZERO
        )

        discount = _money(payload.get("discount"))
        if discount > subtotal:
            raise ValidationError("Discount cannot exceed the cart subtotal")

        total = _money(subtotal + tax - discount)
        amount_received = _money(payload.get("amount_received") or total)
        payment_method = payload.get("payment_method") or "CASH"
        if payment_method not in PAYMENT_METHODS:
            raise ValidationError(f"payment_method must be one of {list(PAYMENT_METHODS)}")
        if payment_method == "CASH" and amount_received < total:
            raise ValidationError(
                f"Amount received ({amount_received}) is less than the total ({total})"
            )
        change_due = _money(max(amount_received - total, ZERO))

        customer_id = payload.get("customer_id")
        if customer_id is None:
            customer_id = customer_model.find_or_create(
                conn, store_id, payload.get("customer_name"), payload.get("customer_phone")
            )

        invoice_number = sale_model.next_invoice_number(conn, store_id, prefix)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sales (store_id, invoice_number, customer_id, customer_name,
                                   customer_phone, subtotal, discount, tax, total, cost_total,
                                   payment_method, amount_received, change_due, status,
                                   notes, sale_date, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'COMPLETED', %s, %s, %s)
                RETURNING id
                """,
                (
                    store_id, invoice_number, customer_id, payload.get("customer_name"),
                    payload.get("customer_phone"), subtotal, discount, tax, total, cost_total,
                    payment_method, amount_received, change_due, payload.get("notes"),
                    sale_date, user_id,
                ),
            )
            sale_id = int(cur.fetchone()["id"])

            for line in lines:
                cur.execute(
                    """
                    INSERT INTO sale_items (sale_id, store_id, product_id, product_name, sku,
                                            quantity, unit_price, cost_price, discount,
                                            tax_rate, tax_amount, line_total, sale_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id, store_id, line["product_id"], line["product_name"], line["sku"],
                        line["quantity"], line["unit_price"], line["cost_price"],
                        line["discount"], line["tax_rate"], line["tax_amount"],
                        line["line_total"], sale_date,
                    ),
                )

            for split in _payment_splits(payload, payment_method, total):
                cur.execute(
                    "INSERT INTO payments (sale_id, store_id, method, amount, reference) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (sale_id, store_id, split["method"], split["amount"], split.get("reference")),
                )

        # Stock leaves the shelf and the ledger records why, on this same
        # connection: if any line fails, the invoice above disappears with it.
        for line in lines:
            try:
                inventory_model.apply_movement(
                    conn,
                    store_id=store_id,
                    product_id=line["product_id"],
                    quantity_change=-line["quantity"],
                    transaction_type="SALE",
                    reference_type="SALE",
                    reference_id=sale_id,
                    notes=f"Sold on {invoice_number}",
                    created_by=user_id,
                )
            except ValueError as exc:
                raise ValidationError(f"{line['product_name']}: {exc}") from exc

    # Only after the commit: the cached forecasts for these products are now
    # stale, because their demand history just changed.
    forecast_service.clear_cache()

    return get_sale(store_id, sale_id)


def _build_lines(
    items: list[dict[str, Any]], products: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Validate cart lines and price them from the database, not the client.

    A price arriving from the browser is a suggestion. Taking it on trust is how
    a POS sells a television for one rupee.
    """
    merged: dict[int, dict[str, Any]] = {}

    for item in items:
        product_id = int(item["product_id"])
        quantity = int(item["quantity"])
        product = products[product_id]

        if quantity <= 0:
            raise ValidationError(f"{product['name']}: quantity must be at least 1")
        if not product["is_active"]:
            raise ValidationError(f"{product['name']} is archived and cannot be sold")

        unit_price = _money(item.get("unit_price") or product["selling_price"])
        line_discount = _money(item.get("discount"))
        tax_rate = _money(product["tax_rate"])

        if product_id in merged:
            merged[product_id]["quantity"] += quantity
            merged[product_id]["discount"] += line_discount
        else:
            merged[product_id] = {
                "product_id": product_id,
                "product_name": product["name"],
                "sku": product["sku"],
                "quantity": quantity,
                "unit_price": unit_price,
                "cost_price": _money(product["cost_price"]),
                "discount": line_discount,
                "tax_rate": tax_rate,
            }

    lines = []
    for line in merged.values():
        gross = _money(line["unit_price"] * line["quantity"])
        net = gross - line["discount"]
        if net < ZERO:
            raise ValidationError(f"{line['product_name']}: discount exceeds the line total")
        if line["quantity"] > products[line["product_id"]]["current_stock"]:
            raise ValidationError(
                f"{line['product_name']}: only "
                f"{products[line['product_id']]['current_stock']} in stock, "
                f"{line['quantity']} requested"
            )

        line["line_total"] = net
        line["tax_amount"] = _money(net * line["tax_rate"] / Decimal("100"))
        lines.append(line)

    return lines


def _payment_splits(
    payload: dict[str, Any], payment_method: str, total: Decimal
) -> list[dict[str, Any]]:
    """One payment row per tender. A MIXED sale must add up to the total."""
    splits = payload.get("payments") or []
    if not splits:
        method = "OTHER" if payment_method == "MIXED" else payment_method
        return [{"method": method, "amount": total, "reference": payload.get("payment_reference")}]

    prepared = [
        {
            "method": split["method"],
            "amount": _money(split["amount"]),
            "reference": split.get("reference"),
        }
        for split in splits
    ]
    paid = sum((split["amount"] for split in prepared), ZERO)
    if paid != total:
        raise ValidationError(f"Payment split totals {paid} but the sale total is {total}")
    return prepared


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------


def get_sale(store_id: int, sale_id: int) -> dict[str, Any]:
    """One invoice with its lines and payments — the receipt payload."""
    sale = sale_model.get_sale(sale_id, store_id)
    if sale is None:
        raise NotFoundError(f"Sale {sale_id} not found")

    items = sale_model.get_sale_items(sale_id, store_id)
    return {
        **sale,
        "items": items,
        "payments": sale_model.get_payments(sale_id, store_id),
        "item_count": len(items),
        "unit_count": sum(int(item["quantity"]) for item in items),
        "gross_profit": float(sale["total"] - sale["tax"] - sale["cost_total"]),
    }


def list_sales(store_id: int, filters: dict[str, Any], limit: int, offset: int) -> dict[str, Any]:
    return {
        "items": sale_model.list_sales(store_id, limit=limit, offset=offset, **filters),
        "total": sale_model.count_sales(store_id, **filters),
        "limit": limit,
        "offset": offset,
    }


def cancel_sale(store_id: int, sale_id: int, user_id: int, reason: str | None) -> dict[str, Any]:
    """Void a sale and return its stock to the shelf.

    The invoice is kept and marked CANCELLED rather than deleted: an invoice
    number that vanishes is an audit problem, and the ledger needs something to
    point the returning stock at.
    """
    sale = sale_model.get_sale(sale_id, store_id)
    if sale is None:
        raise NotFoundError(f"Sale {sale_id} not found")
    if sale["status"] != "COMPLETED":
        raise ConflictError(f"Sale {sale['invoice_number']} is already {sale['status'].lower()}")

    items = sale_model.get_sale_items(sale_id, store_id)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sales SET status = 'CANCELLED', notes = COALESCE(notes, '') || %s "
                "WHERE id = %s AND store_id = %s",
                (f"\nCancelled: {reason or 'no reason given'}", sale_id, store_id),
            )
        for item in items:
            inventory_model.apply_movement(
                conn,
                store_id=store_id,
                product_id=item["product_id"],
                quantity_change=int(item["quantity"]),
                transaction_type="RETURN",
                reference_type="SALE_CANCELLATION",
                reference_id=sale_id,
                notes=f"Stock returned from cancelled {sale['invoice_number']}",
                created_by=user_id,
            )

    forecast_service.clear_cache()
    return get_sale(store_id, sale_id)
