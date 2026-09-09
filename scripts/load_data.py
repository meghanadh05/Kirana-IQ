"""Load the generated CSVs into PostgreSQL.

Usage:
    python scripts/load_data.py             # refuse if data already present
    python scripts/load_data.py --truncate  # wipe products/sales first

Uses COPY for the sales table, which is dramatically faster than row-by-row
inserts for the ~11k rows the generator produces.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Locally the app package sits in <repo>/backend. Inside the container the
# script is mounted at /scripts and the package is already on PYTHONPATH.
_BACKEND = ROOT / "backend"
if _BACKEND.is_dir():
    sys.path.insert(0, str(_BACKEND))

from app.database import close_pool, get_connection, init_db, query_one  # noqa: E402

DATA_DIR = ROOT / "data"
PRODUCTS_CSV = DATA_DIR / "products.csv"
SALES_CSV = DATA_DIR / "sales.csv"


def load_products(conn) -> dict[str, int]:
    """Insert products, returning a {sku: id} map. Existing SKUs are left alone."""
    with PRODUCTS_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO products
                    (sku, name, category, unit_price, current_stock, reorder_level, lead_time_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sku) DO NOTHING
                """,
                (
                    row["sku"],
                    row["name"],
                    row["category"],
                    row["unit_price"],
                    row["current_stock"],
                    row["reorder_level"],
                    row["lead_time_days"],
                ),
            )
        cur.execute("SELECT sku, id FROM products")
        return {r["sku"]: r["id"] for r in cur.fetchall()}


def load_sales(conn, sku_to_id: dict[str, int]) -> int:
    with SALES_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        count = 0
        with conn.cursor() as cur:
            with cur.copy(
                "COPY sales (product_id, quantity, sale_date, unit_price) FROM STDIN"
            ) as copy:
                for row in reader:
                    product_id = sku_to_id.get(row["sku"])
                    if product_id is None:
                        continue
                    copy.write_row(
                        (product_id, int(row["quantity"]), row["sale_date"], row["unit_price"])
                    )
                    count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Load generated CSVs into PostgreSQL.")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing products and sales before loading",
    )
    args = parser.parse_args()

    for path in (PRODUCTS_CSV, SALES_CSV):
        if not path.exists():
            sys.exit(f"Missing {path}. Run: python scripts/generate_data.py")

    init_db()

    existing = query_one("SELECT COUNT(*) AS n FROM products")
    if existing and existing["n"] > 0 and not args.truncate:
        sys.exit(
            f"Database already holds {existing['n']} products. "
            "Re-run with --truncate to replace them."
        )

    with get_connection() as conn:
        if args.truncate:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE sales, products RESTART IDENTITY CASCADE")
            print("Truncated products and sales")

        sku_to_id = load_products(conn)
        print(f"Products loaded: {len(sku_to_id)}")

        sales_count = load_sales(conn, sku_to_id)
        print(f"Sales rows loaded: {sales_count:,}")

    summary = query_one(
        """
        SELECT COUNT(*) AS rows,
               SUM(quantity) AS units,
               MIN(sale_date) AS first_day,
               MAX(sale_date) AS last_day
        FROM sales
        """
    )
    print(
        f"Database now holds {summary['rows']:,} sales rows "
        f"({summary['units']:,} units) from {summary['first_day']} to {summary['last_day']}"
    )


if __name__ == "__main__":
    try:
        main()
    finally:
        # Release pooled connections so the script exits cleanly.
        close_pool()
