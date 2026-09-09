"""Downloadable reports.

Every report is generated from the same queries the screens use, so a CSV and
the page it came from can never disagree.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any, Callable

from app.errors import ValidationError
from app.models import expense as expense_model
from app.models import inventory as inventory_model
from app.models import product as product_model
from app.models import purchase as purchase_model
from app.models import sale as sale_model
from app.services import business_service


def _csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def daily_sales(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "date": row["date"].isoformat(),
            "orders": int(row["orders"]),
            "revenue": round(float(row["revenue"]), 2),
            "tax": round(float(row["tax"]), 2),
            "cost_of_goods": round(float(row["cost"]), 2),
            "gross_profit": round(
                float(row["revenue"]) - float(row["tax"]) - float(row["cost"]), 2
            ),
        }
        for row in sale_model.revenue_series(store_id, start, end)
    ]
    return _csv(rows, ["date", "orders", "revenue", "tax", "cost_of_goods", "gross_profit"])


def invoices(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "invoice_number": row["invoice_number"],
            "date": row["sale_date"].isoformat(),
            "customer": row["customer_name"] or "",
            "items": int(row["item_count"]),
            "units": int(row["unit_count"]),
            "subtotal": float(row["subtotal"]),
            "discount": float(row["discount"]),
            "tax": float(row["tax"]),
            "total": float(row["total"]),
            "payment_method": row["payment_method"],
            "status": row["status"],
        }
        for row in sale_model.list_sales(store_id, start_date=start, end_date=end, limit=10000)
    ]
    return _csv(
        rows,
        ["invoice_number", "date", "customer", "items", "units", "subtotal",
         "discount", "tax", "total", "payment_method", "status"],
    )


def product_sales(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "units_sold": int(row["total_units"]),
            "revenue": round(float(row["total_revenue"]), 2),
            "cost_of_goods": round(float(row["total_cost"]), 2),
            "gross_profit": round(float(row["gross_profit"]), 2),
            "current_stock": int(row["current_stock"]),
        }
        for row in sale_model.product_performance(store_id, start, end, limit=10000)
    ]
    return _csv(
        rows,
        ["sku", "name", "category", "units_sold", "revenue", "cost_of_goods",
         "gross_profit", "current_stock"],
    )


def inventory(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "unit": row["unit"],
            "current_stock": int(row["current_stock"]),
            "reorder_level": int(row["reorder_level"]),
            "stock_status": row["stock_status"],
            "cost_price": float(row["cost_price"]),
            "selling_price": float(row["selling_price"]),
            "stock_value": round(float(row["stock_value"]), 2),
        }
        for row in inventory_model.stock_status_rows(store_id, limit=10000)
    ]
    return _csv(
        rows,
        ["sku", "name", "category", "unit", "current_stock", "reorder_level",
         "stock_status", "cost_price", "selling_price", "stock_value"],
    )


def low_stock(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "sku": row["sku"],
            "name": row["name"],
            "category": row["category"],
            "current_stock": int(row["current_stock"]),
            "reorder_level": int(row["reorder_level"]),
            "lead_time_days": int(row["lead_time_days"]),
            "stock_status": row["stock_status"],
        }
        for row in inventory_model.stock_status_rows(store_id, limit=10000)
        if row["stock_status"] != "OK"
    ]
    return _csv(
        rows,
        ["sku", "name", "category", "current_stock", "reorder_level",
         "lead_time_days", "stock_status"],
    )


def profit(store_id: int, start: date, end: date) -> str:
    summary = business_service.profit_summary(store_id, start, end)
    rows = [
        {"metric": "Revenue (incl. tax)", "amount": summary["revenue"]},
        {"metric": "Tax collected", "amount": summary["tax"]},
        {"metric": "Net revenue", "amount": summary["net_revenue"]},
        {"metric": "Cost of goods sold", "amount": summary["cost_of_goods"]},
        {"metric": "Gross profit", "amount": summary["gross_profit"]},
        {"metric": "Recorded expenses", "amount": summary["recorded_expenses"]},
        {"metric": "Estimated operating profit", "amount": summary["estimated_operating_profit"]},
    ]
    rows.extend(
        {"metric": f"Expense: {row['category']}", "amount": row["total"]}
        for row in summary["expense_breakdown"]
    )
    return _csv(rows, ["metric", "amount"])


def tax(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "tax_rate": float(row["tax_rate"]),
            "taxable_value": round(float(row["taxable_value"]), 2),
            "tax_collected": round(float(row["tax_collected"]), 2),
            "invoices": int(row["invoices"]),
        }
        for row in sale_model.tax_summary(store_id, start, end)
    ]
    return _csv(rows, ["tax_rate", "taxable_value", "tax_collected", "invoices"])


def purchases(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "po_number": row["po_number"],
            "supplier": row["supplier_name"] or "",
            "status": row["status"],
            "items": int(row["item_count"]),
            "units_ordered": int(row["unit_count"]),
            "units_received": int(row["received_count"]),
            "subtotal": float(row["subtotal"]),
            "tax": float(row["tax"]),
            "total": float(row["total"]),
            "created": row["created_at"].date().isoformat(),
            "expected_delivery": row["expected_delivery"].isoformat() if row["expected_delivery"] else "",
        }
        for row in purchase_model.list_orders(store_id, limit=10000)
    ]
    return _csv(
        rows,
        ["po_number", "supplier", "status", "items", "units_ordered", "units_received",
         "subtotal", "tax", "total", "created", "expected_delivery"],
    )


def expenses(store_id: int, start: date, end: date) -> str:
    rows = [
        {
            "date": row["expense_date"].isoformat(),
            "category": row["category"],
            "description": row["description"] or "",
            "amount": float(row["amount"]),
            "payment_method": row["payment_method"],
        }
        for row in expense_model.list_expenses(store_id, start, end, limit=10000)
    ]
    return _csv(rows, ["date", "category", "description", "amount", "payment_method"])


REPORTS: dict[str, dict[str, Any]] = {
    "daily-sales": {"label": "Daily sales", "build": daily_sales,
                    "description": "Revenue, orders and gross profit per day."},
    "invoices": {"label": "Invoices", "build": invoices,
                 "description": "Every invoice in the period with its totals."},
    "product-sales": {"label": "Product sales", "build": product_sales,
                      "description": "Units, revenue and profit per product."},
    "inventory": {"label": "Inventory", "build": inventory,
                  "description": "Current stock and valuation for every product."},
    "low-stock": {"label": "Low stock", "build": low_stock,
                  "description": "Products at or below their reorder level."},
    "profit": {"label": "Profit summary", "build": profit,
               "description": "Gross profit and estimated operating profit."},
    "tax": {"label": "Tax summary", "build": tax,
            "description": "Taxable value and tax collected per rate."},
    "purchases": {"label": "Purchase orders", "build": purchases,
                  "description": "Every purchase order and its receiving status."},
    "expenses": {"label": "Expenses", "build": expenses,
                 "description": "Recorded expenses by date and category."},
}


def build(report: str, store_id: int, start: date, end: date) -> str:
    if report not in REPORTS:
        raise ValidationError(f"Unknown report '{report}'. Available: {list(REPORTS)}")
    builder: Callable[..., str] = REPORTS[report]["build"]
    return builder(store_id, start, end)


def catalogue() -> list[dict[str, str]]:
    return [
        {"id": key, "label": value["label"], "description": value["description"]}
        for key, value in REPORTS.items()
    ]
