"""Generate a realistic synthetic sales dataset for Kirana-IQ.

The generator is fully reproducible: the same --seed always produces the same
CSVs. Output:

    data/products.csv   one row per SKU
    data/sales.csv      one row per product per day that had sales

Demand for a product on a day is drawn from a Poisson distribution whose mean is
built from interpretable multiplicative components:

    lambda = base_demand
             * day_of_week_factor      (weekend uplift, category dependent)
             * seasonal_factor         (slow annual sine wave)
             * trend_factor            (linear growth/decline over the period)
             * event_factor            (festival spikes from data/events.csv)
             * payday_factor           (month-start salary effect)

Because every component is explicit, the resulting series has structure a
forecasting model can actually learn, instead of pure noise.
"""

from __future__ import annotations

import argparse
import csv
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EVENTS_PATH = DATA_DIR / "events.csv"

# (name, unit_price, base_daily_demand, category)
PRODUCT_CATALOGUE: list[tuple[str, float, float, str]] = [
    # Dairy — high volume, strong weekend effect, short shelf life
    ("Amul Taaza Milk 1L", 33.0, 48.0, "Dairy"),
    ("Amul Gold Milk 500ml", 20.0, 36.0, "Dairy"),
    ("Amul Butter 100g", 62.0, 14.0, "Dairy"),
    ("Nestle Dahi 400g", 45.0, 18.0, "Dairy"),
    ("Amul Cheese Slices 200g", 130.0, 6.0, "Dairy"),
    ("Paneer Fresh 200g", 95.0, 9.0, "Dairy"),
    # Snacks — festival and weekend sensitive
    ("Lays Classic Salted 52g", 20.0, 40.0, "Snacks"),
    ("Kurkure Masala Munch 90g", 20.0, 32.0, "Snacks"),
    ("Haldiram Aloo Bhujia 200g", 55.0, 15.0, "Snacks"),
    ("Parle-G Biscuit 250g", 30.0, 44.0, "Snacks"),
    ("Britannia Good Day 200g", 45.0, 20.0, "Snacks"),
    ("Bingo Mad Angles 80g", 20.0, 24.0, "Snacks"),
    # Beverages — strong summer seasonality
    ("Coca-Cola 750ml", 40.0, 28.0, "Beverages"),
    ("Thums Up 1.25L", 65.0, 16.0, "Beverages"),
    ("Frooti Mango 600ml", 40.0, 22.0, "Beverages"),
    ("Tata Tea Gold 500g", 275.0, 8.0, "Beverages"),
    ("Nescafe Classic 50g", 190.0, 5.0, "Beverages"),
    ("Bisleri Water 1L", 20.0, 35.0, "Beverages"),
    # Rice & Grains — steady staples, bulk festival buying
    ("India Gate Basmati 5kg", 620.0, 3.0, "Rice & Grains"),
    ("Aashirvaad Atta 5kg", 260.0, 7.0, "Rice & Grains"),
    ("Toor Dal 1kg", 165.0, 11.0, "Rice & Grains"),
    ("Sona Masoori Rice 10kg", 540.0, 2.5, "Rice & Grains"),
    ("Fortune Sunflower Oil 1L", 145.0, 13.0, "Rice & Grains"),
    # Personal Care — low volume, weak weekly pattern
    ("Colgate Strong Teeth 200g", 110.0, 7.0, "Personal Care"),
    ("Dove Soap 100g", 62.0, 12.0, "Personal Care"),
    ("Clinic Plus Shampoo 175ml", 120.0, 6.0, "Personal Care"),
    # Household — festival cleaning spikes
    ("Surf Excel Easy Wash 1kg", 130.0, 9.0, "Household"),
    ("Vim Dishwash Bar 200g", 20.0, 26.0, "Household"),
    ("Harpic Toilet Cleaner 500ml", 95.0, 5.0, "Household"),
    # Bakery — daily fresh, weekend heavy
    ("Britannia Bread 400g", 45.0, 30.0, "Bakery"),
]

# Category-level behavioural knobs.
CATEGORY_PROFILE: dict[str, dict[str, float]] = {
    #                    weekend uplift   summer peak   annual amplitude
    "Dairy":         {"weekend": 1.15, "peak_month": 5.0,  "seasonality": 0.08},
    "Snacks":        {"weekend": 1.35, "peak_month": 11.0, "seasonality": 0.12},
    "Beverages":     {"weekend": 1.25, "peak_month": 5.0,  "seasonality": 0.35},
    "Rice & Grains": {"weekend": 1.10, "peak_month": 10.0, "seasonality": 0.10},
    "Personal Care": {"weekend": 1.05, "peak_month": 7.0,  "seasonality": 0.05},
    "Household":     {"weekend": 1.20, "peak_month": 10.0, "seasonality": 0.10},
    "Bakery":        {"weekend": 1.30, "peak_month": 1.0,  "seasonality": 0.08},
}

CATEGORY_CODE = {
    "Dairy": "DRY",
    "Snacks": "SNK",
    "Beverages": "BEV",
    "Rice & Grains": "GRN",
    "Personal Care": "PCR",
    "Household": "HHD",
    "Bakery": "BKY",
}


def load_events(path: Path) -> list[dict]:
    """Read data/events.csv. Returns [] when the file is absent."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {
                "date": date.fromisoformat(row["date"]),
                "event_name": row["event_name"],
                "affected_category": row["affected_category"],
                "impact_score": float(row["impact_score"]),
            }
            for row in csv.DictReader(handle)
        ]


def event_factor(day: date, category: str, events: list[dict]) -> float:
    """Demand multiplier for a festival.

    Shoppers stock up *before* a festival, so the uplift ramps over the three
    days leading up to the event and decays the day after.
    """
    factor = 1.0
    for event in events:
        if event["affected_category"] not in (category, "ALL"):
            continue
        offset = (event["date"] - day).days
        if offset == 0:
            weight = 1.0
        elif offset == 1:
            weight = 0.9
        elif offset == 2:
            weight = 0.6
        elif offset == 3:
            weight = 0.35
        elif offset == -1:
            weight = 0.3
        else:
            continue
        factor *= 1.0 + event["impact_score"] * weight
    return factor


def build_products(rng: np.random.Generator) -> list[dict]:
    products = []
    per_category_index: dict[str, int] = {}
    for name, price, base_demand, category in PRODUCT_CATALOGUE:
        per_category_index[category] = per_category_index.get(category, 0) + 1
        sku = f"{CATEGORY_CODE[category]}-{per_category_index[category]:03d}"
        products.append(
            {
                "sku": sku,
                "name": name,
                "category": category,
                "unit_price": round(price, 2),
                "base_demand": base_demand,
                # Trend over the whole window: mostly flat, some clear movers.
                "trend": float(rng.normal(0.0, 0.18)),
                # Per-product noise level (Poisson gives the rest).
                "noise": float(rng.uniform(0.06, 0.18)),
                "lead_time_days": int(rng.integers(1, 8)),
            }
        )
    return products


def generate_sales(
    products: list[dict],
    start: date,
    end: date,
    events: list[dict],
    rng: np.random.Generator,
) -> list[dict]:
    rows: list[dict] = []
    total_days = (end - start).days + 1

    for product in products:
        profile = CATEGORY_PROFILE[product["category"]]
        for offset in range(total_days):
            day = start + timedelta(days=offset)

            # Weekly pattern: Sat/Sun uplift, Monday dip.
            weekday = day.weekday()
            if weekday >= 5:
                dow = profile["weekend"]
            elif weekday == 0:
                dow = 0.92
            else:
                dow = 1.0

            # Annual seasonality as a sine wave peaking in the category's month.
            phase = 2 * math.pi * (day.timetuple().tm_yday / 365.25)
            peak_phase = 2 * math.pi * ((profile["peak_month"] - 1) * 30.4 / 365.25)
            seasonal = 1.0 + profile["seasonality"] * math.cos(phase - peak_phase)

            # Linear trend across the full window.
            trend = 1.0 + product["trend"] * (offset / total_days)

            # Salary effect: first five days of the month run hot.
            payday = 1.12 if day.day <= 5 else 1.0

            events_mult = event_factor(day, product["category"], events)

            noise = float(rng.normal(1.0, product["noise"]))
            lam = product["base_demand"] * dow * seasonal * trend * payday * events_mult * noise
            lam = max(lam, 0.05)

            quantity = int(rng.poisson(lam))
            if quantity <= 0:
                continue

            # Occasional small discount so unit_price is not a constant.
            price = product["unit_price"]
            if rng.random() < 0.04:
                price = round(price * float(rng.uniform(0.85, 0.95)), 2)

            rows.append(
                {
                    "sku": product["sku"],
                    "sale_date": day.isoformat(),
                    "quantity": quantity,
                    "unit_price": price,
                }
            )
    return rows


def assign_stock(products: list[dict], sales: list[dict], end: date, rng: np.random.Generator) -> None:
    """Set current_stock and reorder_level from each product's recent demand.

    Stock levels are drawn so the catalogue contains a realistic mix: a few
    products close to stocking out, most healthy, and a few clearly overstocked.
    That gives the phase-4 inventory logic something meaningful to report.
    """
    window_start = end - timedelta(days=29)
    recent: dict[str, list[int]] = {p["sku"]: [] for p in products}
    for row in sales:
        if date.fromisoformat(row["sale_date"]) >= window_start:
            recent[row["sku"]].append(row["quantity"])

    # Cover-days buckets: ~20% tight, ~60% healthy, ~20% overstocked.
    for product in products:
        quantities = recent[product["sku"]]
        avg_daily = sum(quantities) / 30.0 if quantities else 0.5

        draw = rng.random()
        if draw < 0.20:
            cover_days = float(rng.uniform(0.5, 3.0))
        elif draw < 0.80:
            cover_days = float(rng.uniform(6.0, 20.0))
        else:
            cover_days = float(rng.uniform(35.0, 60.0))

        product["current_stock"] = max(0, int(round(avg_daily * cover_days)))
        # A conventional reorder level: cover the lead time plus three days.
        product["reorder_level"] = max(1, int(round(avg_daily * (product["lead_time_days"] + 3))))
        product["avg_daily_recent"] = round(avg_daily, 2)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Kirana-IQ sales data.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument("--days", type=int, default=365, help="History length in days (default: 365)")
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        default=date(2026, 9, 8),
        help="Last day of history, YYYY-MM-DD (default: 2026-09-08)",
    )
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)
    end = args.end_date
    start = end - timedelta(days=args.days - 1)

    events = load_events(EVENTS_PATH)
    if not events:
        print(f"WARNING: no events loaded from {EVENTS_PATH}; festival spikes disabled")

    products = build_products(rng)
    sales = generate_sales(products, start, end, events, rng)
    assign_stock(products, sales, end, rng)

    write_csv(
        DATA_DIR / "products.csv",
        products,
        ["sku", "name", "category", "unit_price", "current_stock", "reorder_level", "lead_time_days"],
    )
    write_csv(DATA_DIR / "sales.csv", sales, ["sku", "sale_date", "quantity", "unit_price"])

    total_units = sum(row["quantity"] for row in sales)
    print(f"Seed:        {args.seed}")
    print(f"Date range:  {start} -> {end} ({args.days} days)")
    print(f"Products:    {len(products)} across {len(CATEGORY_PROFILE)} categories")
    print(f"Events:      {len(events)}")
    print(f"Sales rows:  {len(sales):,}")
    print(f"Total units: {total_units:,}")
    print(f"Written to:  {DATA_DIR/'products.csv'}, {DATA_DIR/'sales.csv'}")


if __name__ == "__main__":
    main()
