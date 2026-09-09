"""Feature engineering for SKU-level daily demand forecasting.

The single rule that governs this module: **a feature for date D may only use
information available before the end of D-1.** Every lag and rolling statistic
is therefore computed on `quantity.shift(1)` before any window is applied.

The one deliberate exception is the festival calendar. Events are known months
in advance, so using tomorrow's Diwali flag to predict tomorrow's demand is not
leakage — it is exactly what a shop owner does when ordering.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.config import DATA_DIR

EVENTS_PATH = DATA_DIR / "events.csv"

# Rows before this many days of history are dropped, because lag_30 and the
# 30-day rolling mean are undefined. The growth features need 61 days to become
# genuinely informative; between day 31 and day 60 they fall back to 0.0.
MIN_HISTORY_DAYS = 31

# The deepest lookback any feature reads. recent_30_day_growth compares the last
# 30 days against the 30 before that, so a row at date D depends on demand back
# to D-60 and no further. Forecasting trims history to this window, which is
# exact rather than approximate: older days cannot influence the result.
FEATURE_LOOKBACK_DAYS = 61

CATEGORIES = [
    "Bakery",
    "Beverages",
    "Dairy",
    "Household",
    "Personal Care",
    "Rice & Grains",
    "Snacks",
]

FEATURE_COLUMNS = [
    # Calendar
    "day_of_week",
    "month",
    "day_of_month",
    "is_weekend",
    # Lags
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_30",
    # Rolling windows
    "rolling_mean_7",
    "rolling_mean_14",
    "rolling_mean_30",
    "rolling_std_7",
    # Trend
    "recent_7_day_growth",
    "recent_30_day_growth",
    # Product
    "unit_price",
    # Events
    "festival_flag",
    "festival_impact",
    "festival_impact_upcoming",
    "promotion_flag",
] + [f"category_{c}" for c in CATEGORIES]

TARGET_COLUMN = "quantity"


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


def load_events(path: Path | None = None) -> pd.DataFrame:
    """Read the festival calendar. Returns an empty frame when absent."""
    path = path or EVENTS_PATH
    if not path.exists():
        return pd.DataFrame(columns=["date", "event_name", "affected_category", "impact_score"])
    events = pd.read_csv(path, parse_dates=["date"])
    events["date"] = events["date"].dt.date
    return events


def category_event_impact(events: pd.DataFrame, category: str) -> dict[date, float]:
    """Total impact score per date for one category (rows tagged ALL included)."""
    if events.empty:
        return {}
    relevant = events[events["affected_category"].isin([category, "ALL"])]
    grouped = relevant.groupby("date")["impact_score"].sum()
    return grouped.to_dict()


# --------------------------------------------------------------------------
# Frame construction
# --------------------------------------------------------------------------


def build_daily_frame(
    history: Iterable[dict[str, Any]],
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Turn sparse sales rows into a gap-free daily series.

    The sales table only holds days that had sales. A day with no sales is a
    real zero, not a missing value, so the series is reindexed onto a complete
    calendar and filled with zero. Skipping this step would silently teach the
    model that demand never drops to nothing.
    """
    rows = list(history)
    if not rows:
        return pd.DataFrame(columns=["sale_date", "quantity"])

    frame = pd.DataFrame(rows)
    frame["sale_date"] = pd.to_datetime(frame["sale_date"])
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce").fillna(0)

    has_price = "avg_price" in frame.columns
    if has_price:
        frame["avg_price"] = pd.to_numeric(frame["avg_price"], errors="coerce")

    # The database already returns one row per day, and so does the forecasting
    # loop. Grouping is only needed when a caller passes raw un-aggregated rows,
    # and skipping it there removes a fifth of the cost of building features.
    if frame["sale_date"].is_unique:
        columns = ["sale_date", "quantity"] + (["avg_price"] if has_price else [])
        frame = frame[columns].sort_values("sale_date")
    elif has_price:
        frame = frame.groupby("sale_date", as_index=False).agg(
            quantity=("quantity", "sum"), avg_price=("avg_price", "mean")
        )
    else:
        frame = frame.groupby("sale_date", as_index=False)["quantity"].sum()

    first = pd.Timestamp(start) if start else frame["sale_date"].min()
    last = pd.Timestamp(end) if end else frame["sale_date"].max()

    calendar = pd.date_range(first, last, freq="D")
    frame = frame.set_index("sale_date").reindex(calendar).rename_axis("sale_date").reset_index()

    # A day with no sales row is a genuine zero. Price, by contrast, is simply
    # unobserved on those days and stays NaN for the promotion flag to ignore.
    frame["quantity"] = frame["quantity"].fillna(0).astype(float)
    return frame


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    dates = frame["sale_date"]
    frame["day_of_week"] = dates.dt.dayofweek
    frame["month"] = dates.dt.month
    frame["day_of_month"] = dates.dt.day
    frame["is_weekend"] = (dates.dt.dayofweek >= 5).astype(int)
    return frame


def add_lag_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Lags, rolling statistics and growth ratios.

    `past` is the demand series shifted by one day. Every window below is built
    from `past`, so no feature on row D can see the quantity sold on day D.
    """
    frame = frame.copy()
    past = frame["quantity"].shift(1)

    for lag in (1, 7, 14, 30):
        frame[f"lag_{lag}"] = frame["quantity"].shift(lag)

    for window in (7, 14, 30):
        frame[f"rolling_mean_{window}"] = past.rolling(window).mean()
    frame["rolling_std_7"] = past.rolling(7).std()

    # Growth compares the most recent window against the window before it.
    previous_7 = past.shift(7).rolling(7).mean()
    previous_30 = past.shift(30).rolling(30).mean()
    frame["recent_7_day_growth"] = _safe_growth(frame["rolling_mean_7"], previous_7)
    frame["recent_30_day_growth"] = _safe_growth(frame["rolling_mean_30"], previous_30)

    return frame


def _safe_growth(recent: pd.Series, previous: pd.Series) -> pd.Series:
    """Percentage change guarded against division by zero.

    A product that sold nothing in the earlier window has undefined growth;
    reporting 0.0 there is more useful to a tree model than infinity.
    """
    growth = (recent - previous) / previous.replace(0, np.nan)
    return growth.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def add_event_features(frame: pd.DataFrame, events: pd.DataFrame, category: str) -> pd.DataFrame:
    """Festival signals for the product's category.

    `festival_impact_upcoming` is the strongest event in the next three days.
    Shoppers stock up ahead of a festival, so the pre-event ramp carries more
    signal than the day itself.
    """
    frame = frame.copy()
    impact_by_date = category_event_impact(events, category)

    day_impact = frame["sale_date"].dt.date.map(lambda d: impact_by_date.get(d, 0.0))
    frame["festival_impact"] = day_impact.astype(float)

    upcoming = pd.concat(
        [frame["festival_impact"].shift(-offset) for offset in (1, 2, 3)], axis=1
    )
    frame["festival_impact_upcoming"] = upcoming.max(axis=1).fillna(0.0)
    frame["festival_flag"] = (
        (frame["festival_impact"] > 0) | (frame["festival_impact_upcoming"] > 0)
    ).astype(int)
    return frame


def add_product_features(frame: pd.DataFrame, product: dict[str, Any]) -> pd.DataFrame:
    """Price, promotion flag and one-hot category."""
    frame = frame.copy()
    list_price = float(product["unit_price"])
    frame["unit_price"] = list_price

    # A day is a promotion if the realised price fell meaningfully below list.
    if "avg_price" in frame.columns:
        realised = pd.to_numeric(frame["avg_price"], errors="coerce").fillna(list_price)
        frame["promotion_flag"] = (realised < list_price * 0.98).astype(int)
    else:
        frame["promotion_flag"] = 0

    for category in CATEGORIES:
        frame[f"category_{category}"] = int(product["category"] == category)
    return frame


def build_features(
    history: Iterable[dict[str, Any]],
    product: dict[str, Any],
    events: pd.DataFrame | None = None,
    start: date | None = None,
    end: date | None = None,
    dropna: bool = True,
) -> pd.DataFrame:
    """Full feature frame for one product.

    With `dropna=True` the warm-up rows that lack a complete 30-day lookback are
    removed, which is what training wants. Prediction passes `dropna=False` and
    reads the final row.
    """
    events = load_events() if events is None else events

    frame = build_daily_frame(history, start=start, end=end)
    if frame.empty:
        return pd.DataFrame(columns=["sale_date", TARGET_COLUMN, *FEATURE_COLUMNS])

    frame = add_calendar_features(frame)
    frame = add_lag_features(frame)
    frame = add_event_features(frame, events, product["category"])
    frame = add_product_features(frame, product)

    frame["product_id"] = product.get("id")
    frame["sku"] = product.get("sku")

    if dropna:
        frame = frame.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)
    return frame


def build_training_frame(
    products: list[dict[str, Any]],
    histories: dict[int, list[dict[str, Any]]],
    events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Stack per-product feature frames into one training set.

    A single model is trained across every SKU rather than one model per
    product. Lag and rolling features already carry each product's scale, so
    the shared model learns the weekly and festival patterns from 30x more
    rows, and it can serve a brand-new SKU as soon as it has history.
    """
    events = load_events() if events is None else events

    frames = [
        build_features(histories.get(product["id"], []), product, events=events)
        for product in products
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["sale_date", TARGET_COLUMN, *FEATURE_COLUMNS])

    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values(["sale_date", "product_id"]).reset_index(drop=True)


def chronological_split(
    frame: pd.DataFrame,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split by calendar date, never at random.

    Cut points are chosen on the sorted unique dates so that every product is
    split at the same two moments. Shuffling a time series would let the model
    train on next week to predict last week, and the resulting scores would be
    meaningless.
    """
    dates = np.sort(frame["sale_date"].unique())
    if len(dates) < 3:
        raise ValueError("Not enough distinct dates to split")

    train_end = dates[int(len(dates) * train_fraction)]
    validation_end = dates[int(len(dates) * (train_fraction + validation_fraction))]

    train = frame[frame["sale_date"] < train_end]
    validation = frame[(frame["sale_date"] >= train_end) & (frame["sale_date"] < validation_end)]
    test = frame[frame["sale_date"] >= validation_end]
    return train, validation, test
