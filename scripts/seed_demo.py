"""Populate a store with the generated synthetic dataset.

Usage:
    python scripts/seed_demo.py                    # demo store, demo login
    python scripts/seed_demo.py --store-id 3       # an existing store you own
    python scripts/seed_demo.py --reset            # wipe the store's data first
    python scripts/seed_demo.py --train            # also train the demand model

The generated data lands as real invoices and inventory movements, so a seeded
store behaves exactly like one that was used: the forecasting pipeline reads the
same sale_items a POS checkout writes.

Seeded stores are flagged `is_demo` and the demo account lives on a `demo.`
subdomain, so synthetic data is never mistaken for a real shop's.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Locally the app package sits in <repo>/backend. Inside the container the
# script is mounted at /scripts and the package is already on PYTHONPATH.
_BACKEND = ROOT / "backend"
if _BACKEND.is_dir():
    sys.path.insert(0, str(_BACKEND))

from app.database import close_pool, get_connection, init_db, query_one  # noqa: E402
from app.security import hash_password  # noqa: E402

DATA_DIR = ROOT / "data"
PRODUCTS_CSV = DATA_DIR / "products.csv"
SALES_CSV = DATA_DIR / "sales.csv"

DEMO_EMAIL = "demo@demo.kirana-iq.com"
DEMO_PASSWORD = "demo12345"

SUPPLIERS = [
    ("Sri Venkateswara Distributors", "Dairy", 2),
    ("Balaji Wholesale Traders", "Snacks", 3),
    ("Deccan Beverage Supply", "Beverages", 4),
    ("Annapurna Grains & Rice", "Rice & Grains", 5),
    ("Sunrise FMCG Agencies", "Personal Care", 6),
    ("Metro Household Supplies", "Household", 4),
    ("Daily Fresh Bakery", "Bakery", 1),
]


def ensure_demo_store(conn) -> tuple[int, int]:
    """Return (store_id, user_id) for the demo tenant, creating it if needed."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (email, password_hash, full_name)
            VALUES (%s, %s, 'Demo Owner')
            ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
            RETURNING id
            """,
            (DEMO_EMAIL, hash_password(DEMO_PASSWORD)),
        )
        user_id = int(cur.fetchone()["id"])

        cur.execute("SELECT id FROM stores WHERE is_demo = TRUE ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row:
            store_id = int(row["id"])
        else:
            cur.execute(
                """
                INSERT INTO stores (name, owner_name, city, state, business_type, is_demo,
                                    onboarding_step, onboarding_completed, created_by)
                VALUES ('Demo Store', 'Demo Owner', 'Hyderabad', 'Telangana', 'KIRANA',
                        TRUE, 4, TRUE, %s)
                RETURNING id
                """,
                (user_id,),
            )
            store_id = int(cur.fetchone()["id"])

        cur.execute(
            "INSERT INTO store_members (store_id, user_id, role) VALUES (%s, %s, 'OWNER') "
            "ON CONFLICT (store_id, user_id) DO NOTHING",
            (store_id, user_id),
        )
        cur.execute(
            "INSERT INTO store_settings (store_id) VALUES (%s) ON CONFLICT DO NOTHING",
            (store_id,),
        )
    return store_id, user_id


def reset_store(conn, store_id: int) -> None:
    """Remove this store's transactional data. Other stores are untouched."""
    with conn.cursor() as cur:
        for table in (
            "forecast_predictions", "forecast_runs", "notifications",
            "purchase_order_items", "purchase_orders", "expenses",
            "payments", "sale_items", "sales", "inventory_transactions",
        ):
            cur.execute(f"DELETE FROM {table} WHERE store_id = %s", (store_id,))
        cur.execute("DELETE FROM products WHERE store_id = %s", (store_id,))
        cur.execute("DELETE FROM customers WHERE store_id = %s", (store_id,))
        cur.execute("DELETE FROM suppliers WHERE store_id = %s", (store_id,))
        cur.execute("DELETE FROM categories WHERE store_id = %s", (store_id,))


def load_suppliers(conn, store_id: int) -> dict[str, int]:
    """One supplier per category, so reorder grouping has something to group by."""
    mapping: dict[str, int] = {}
    with conn.cursor() as cur:
        for name, category, lead_time in SUPPLIERS:
            cur.execute(
                "SELECT id FROM suppliers WHERE store_id = %s AND name = %s", (store_id, name)
            )
            row = cur.fetchone()
            if row:
                mapping[category] = int(row["id"])
                continue
            cur.execute(
                """
                INSERT INTO suppliers (store_id, name, contact_person, phone,
                                       default_lead_time_days)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
                """,
                (store_id, name, f"{name.split()[0]} Desk", "9876500000", lead_time),
            )
            mapping[category] = int(cur.fetchone()["id"])
    return mapping


def load_products(conn, store_id: int, suppliers: dict[str, int]) -> dict[str, dict]:
    """Insert the catalogue, returning {sku: product row}. Existing SKUs are left alone."""
    with PRODUCTS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                "INSERT INTO categories (store_id, name) VALUES (%s, %s) "
                "ON CONFLICT (store_id, name) DO NOTHING",
                (store_id, row["category"]),
            )
            cur.execute(
                """
                INSERT INTO products
                    (store_id, sku, barcode, name, brand, category, unit, selling_price,
                     cost_price, tax_rate, current_stock, reorder_level, lead_time_days,
                     supplier_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (store_id, sku) DO NOTHING
                """,
                (
                    store_id, row["sku"], row["barcode"], row["name"], row["brand"],
                    row["category"], row["unit"], row["selling_price"], row["cost_price"],
                    row["tax_rate"], row["current_stock"], row["reorder_level"],
                    row["lead_time_days"], suppliers.get(row["category"]),
                ),
            )

        cur.execute(
            "SELECT id, sku, name, cost_price, tax_rate, current_stock FROM products "
            "WHERE store_id = %s",
            (store_id,),
        )
        return {r["sku"]: r for r in cur.fetchall()}


def load_sales(conn, store_id: int, user_id: int, products: dict[str, dict]) -> int:
    """Replay the generated daily sales as invoices and line items.

    One invoice per day rather than per row: a day's sales across the catalogue
    are what a shop's till roll actually looks like, and the demand aggregation
    that feeds the model reads line items either way.
    """
    with SALES_CSV.open(newline="", encoding="utf-8") as handle:
        by_day: dict[str, list[dict]] = defaultdict(list)
        for row in csv.DictReader(handle):
            if int(row["quantity"]) > 0 and row["sku"] in products:
                by_day[row["sale_date"]].append(row)

    written = 0
    with conn.cursor() as cur:
        for sequence, (sale_date, rows) in enumerate(sorted(by_day.items()), start=1):
            subtotal = tax = cost_total = 0.0
            lines = []
            for row in rows:
                product = products[row["sku"]]
                quantity = int(row["quantity"])
                unit_price = float(row["unit_price"])
                line_total = round(quantity * unit_price, 2)
                tax_rate = float(product["tax_rate"])
                # The generated price is tax-inclusive shelf price, so the tax
                # component is extracted from it rather than added on top.
                tax_amount = round(line_total - line_total / (1 + tax_rate / 100), 2)

                subtotal += line_total
                tax += tax_amount
                cost_total += quantity * float(product["cost_price"])
                lines.append(
                    (product, row["sku"], quantity, unit_price, tax_rate, tax_amount, line_total)
                )

            cur.execute(
                """
                INSERT INTO sales (store_id, invoice_number, subtotal, tax, total, cost_total,
                                   payment_method, amount_received, status, sale_date, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, 'CASH', %s, 'COMPLETED', %s, %s)
                RETURNING id
                """,
                (
                    store_id, f"DEMO-{sequence:05d}", round(subtotal, 2), round(tax, 2),
                    round(subtotal, 2), round(cost_total, 2), round(subtotal, 2),
                    sale_date, user_id,
                ),
            )
            sale_id = int(cur.fetchone()["id"])

            for product, sku, quantity, unit_price, tax_rate, tax_amount, line_total in lines:
                cur.execute(
                    """
                    INSERT INTO sale_items (sale_id, store_id, product_id, product_name, sku,
                                            quantity, unit_price, cost_price, tax_rate,
                                            tax_amount, line_total, sale_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        sale_id, store_id, product["id"], product["name"], sku,
                        quantity, unit_price, product["cost_price"], tax_rate,
                        tax_amount, line_total, sale_date,
                    ),
                )
                written += 1
    return written


def load_opening_stock(conn, store_id: int) -> None:
    """Record current stock as an opening balance so the ledger explains it."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO inventory_transactions (store_id, product_id, type, quantity_change,
                                                quantity_before, quantity_after,
                                                reference_type, notes)
            SELECT %s, id, 'OPENING_STOCK', current_stock, 0, current_stock,
                   'DEMO_SEED', 'Opening stock from the demo dataset'
            FROM products p
            WHERE p.store_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM inventory_transactions t
                  WHERE t.product_id = p.id AND t.type = 'OPENING_STOCK')
            """,
            (store_id, store_id),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a store with the demo dataset.")
    parser.add_argument("--store-id", type=int, default=None,
                        help="Seed this store instead of the demo store.")
    parser.add_argument("--reset", action="store_true",
                        help="Delete the store's existing data before loading.")
    parser.add_argument("--train", action="store_true",
                        help="Train the demand model after loading.")
    args = parser.parse_args()

    for path in (PRODUCTS_CSV, SALES_CSV):
        if not path.exists():
            sys.exit(f"Missing {path}. Run: python scripts/generate_data.py")

    init_db()

    with get_connection() as conn:
        if args.store_id is None:
            store_id, user_id = ensure_demo_store(conn)
            print(f"Demo store {store_id} ready (login {DEMO_EMAIL} / {DEMO_PASSWORD})")
        else:
            store_id = args.store_id
            row = query_one(
                "SELECT user_id FROM store_members WHERE store_id = %s AND role = 'OWNER' "
                "ORDER BY id LIMIT 1",
                (store_id,),
            )
            if row is None:
                sys.exit(f"Store {store_id} does not exist or has no owner.")
            user_id = int(row["user_id"])

        if args.reset:
            reset_store(conn, store_id)
            print("Existing store data removed")

        # Checked on this connection, not a fresh one: --reset has deleted the
        # old rows but not yet committed, and a second connection would still
        # see them and refuse.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM sale_items WHERE store_id = %s", (store_id,)
            )
            existing = int(cur.fetchone()["n"])
        if existing:
            sys.exit(
                f"Store {store_id} already holds {existing:,} sale lines. "
                "Re-run with --reset to replace them."
            )

        suppliers = load_suppliers(conn, store_id)
        products = load_products(conn, store_id, suppliers)
        print(f"Products loaded: {len(products)}")

        load_opening_stock(conn, store_id)
        lines = load_sales(conn, store_id, user_id, products)
        print(f"Sale lines loaded: {lines:,}")

    summary = query_one(
        """
        SELECT COUNT(DISTINCT sale_id) AS invoices, COUNT(*) AS lines,
               SUM(quantity) AS units, MIN(sale_date) AS first_day, MAX(sale_date) AS last_day
        FROM sale_items WHERE store_id = %s
        """,
        (store_id,),
    )
    print(
        f"Store {store_id} now holds {summary['invoices']:,} invoices / "
        f"{summary['lines']:,} lines ({summary['units']:,} units) "
        f"from {summary['first_day']} to {summary['last_day']}"
    )

    if args.train:
        from app.ml.train_model import train

        print("\nTraining the demand model...")
        report = train(store_id=store_id, shared=True)
        print(f"Selected {report['selected_model']}, "
              f"test WAPE {report['test_scores'][report['selected_model']]['wape']:.2f}%")


if __name__ == "__main__":
    try:
        main()
    finally:
        close_pool()
