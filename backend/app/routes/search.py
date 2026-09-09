"""Global search — the ⌘K command bar."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.deps import Store
from app.models import customer as customer_model
from app.models import product as product_model
from app.models import sale as sale_model
from app.models import supplier as supplier_model

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(
    context: Store,
    q: str = Query(min_length=1, max_length=100),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict:
    """Search products, invoices, suppliers and customers in one call.

    Each group is capped so one type of match cannot crowd out the others — a
    search for "10" should not return twenty invoices and nothing else.
    """
    term = q.strip()

    products = product_model.list_products(
        context.store_id, search=term, is_active=None, limit=limit
    )
    sales = sale_model.list_sales(context.store_id, search=term, limit=limit)
    suppliers = supplier_model.list_suppliers(context.store_id, search=term)[:limit]
    customers = customer_model.list_customers(context.store_id, search=term, limit=limit)

    return {
        "query": term,
        "products": [
            {
                "id": row["id"],
                "label": row["name"],
                "sublabel": f"{row['sku']} · {row['current_stock']} in stock",
                "link": f"/products/{row['id']}",
            }
            for row in products
        ],
        "sales": [
            {
                "id": row["id"],
                "label": row["invoice_number"],
                "sublabel": f"{row['sale_date']} · {row['total']}",
                "link": f"/sales/{row['id']}",
            }
            for row in sales
        ],
        "suppliers": [
            {
                "id": row["id"],
                "label": row["name"],
                "sublabel": row["phone"] or row["contact_person"] or "Supplier",
                "link": f"/suppliers/{row['id']}",
            }
            for row in suppliers
        ],
        "customers": [
            {
                "id": row["id"],
                "label": row["name"],
                "sublabel": row["phone"] or row["email"] or "Customer",
                "link": f"/customers/{row['id']}",
            }
            for row in customers
        ],
    }
