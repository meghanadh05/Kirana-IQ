"""Forecast accuracy metrics and the moving-average baseline.

Three metrics are reported throughout the project:

MAE   Mean absolute error, in units. Easy to explain to a shop owner:
      "on average we are off by N packets a day".
RMSE  Root mean squared error, in units. Punishes large misses harder than
      MAE, so a big gap between the two signals occasional bad days.
WAPE  Weighted absolute percentage error: sum|error| / sum(actual). Used
      instead of MAPE because demand series contain zero-sale days, where
      MAPE divides by zero and blows up.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(predicted)) ** 2)))


def wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Absolute error as a fraction of total actual demand.

    Returns NaN when the actual series sums to zero, which is undefined rather
    than perfect.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    denominator = np.sum(np.abs(actual))
    if denominator == 0:
        return float("nan")
    return float(np.sum(np.abs(actual - predicted)) / denominator)


def evaluate(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """All three metrics for one set of predictions."""
    return {
        "mae": mae(actual, predicted),
        "rmse": rmse(actual, predicted),
        "wape": wape(actual, predicted),
    }


def moving_average_baseline(frame: pd.DataFrame, window: int = 7) -> np.ndarray:
    """Baseline forecast: the mean of the previous `window` days.

    `rolling_mean_7` is already the shifted 7-day mean built by the feature
    pipeline, so the baseline is simply that column — no separate computation,
    and it is guaranteed to use the same leakage-free window as the model.
    """
    column = f"rolling_mean_{window}"
    if column not in frame.columns:
        raise KeyError(f"{column} not present; build features before evaluating")
    return frame[column].to_numpy(dtype=float)


def comparison_table(results: dict[str, dict[str, float]]) -> str:
    """Render a metrics dict as a fixed-width table for terminal output."""
    header = f"{'Model':<28}{'MAE':>10}{'RMSE':>10}{'WAPE':>10}"
    lines = [header, "-" * len(header)]
    for name, metrics in results.items():
        lines.append(
            f"{name:<28}{metrics['mae']:>10.3f}{metrics['rmse']:>10.3f}"
            f"{metrics['wape'] * 100:>9.2f}%"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Horizon backtest
# --------------------------------------------------------------------------


def flat_baseline_forecast(history: list[dict], horizon: int) -> float:
    """Baseline prediction for every day of a horizon: the last 7-day mean.

    The moving-average baseline has no notion of a horizon, so it predicts the
    same number for day 1 and day 30. That is precisely the weakness a real
    model should beat.
    """
    import pandas as pd

    ordered = sorted(history, key=lambda r: pd.Timestamp(r["sale_date"]))
    last_date = pd.Timestamp(ordered[-1]["sale_date"])
    window_start = last_date - pd.Timedelta(days=6)
    window = [
        float(r["quantity"])
        for r in ordered
        if window_start <= pd.Timestamp(r["sale_date"]) <= last_date
    ]
    # Divide by 7 days, not by the number of rows: missing days are real zeros.
    return sum(window) / 7.0


def horizon_backtest(horizon: int = 7, origins: int = 8) -> dict:
    """Backtest recursive forecasting against the flat baseline, per horizon step.

    Returns overall metrics for both approaches plus a per-step breakdown that
    shows how error grows as predictions are fed back into the lag features.
    """
    import pandas as pd

    from app.ml.predict import InsufficientHistoryError, forecast, load_model
    from app.ml.feature_engineering import MIN_HISTORY_DAYS, load_events
    from app.models import product as product_model
    from app.models import sale as sale_model

    bundle = load_model()
    events = load_events()
    products = product_model.list_products(limit=1000)

    rows: list[dict] = []
    skipped = 0

    for product in products:
        history = sale_model.daily_history(product["id"])
        if not history:
            skipped += 1
            continue

        ordered = sorted(history, key=lambda r: pd.Timestamp(r["sale_date"]))
        first_date = pd.Timestamp(ordered[0]["sale_date"])
        last_date = pd.Timestamp(ordered[-1]["sale_date"])
        actual_by_date = {
            pd.Timestamp(r["sale_date"]).date(): float(r["quantity"]) for r in ordered
        }

        for index in range(origins):
            cutoff_date = last_date - pd.Timedelta(days=horizon * (index + 1))
            if (cutoff_date - first_date).days + 1 < MIN_HISTORY_DAYS:
                break

            truncated = [r for r in ordered if pd.Timestamp(r["sale_date"]) <= cutoff_date]
            if not truncated:
                break

            try:
                predictions = forecast(
                    truncated, product, days=horizon, events=events, model_bundle=bundle
                )
            except InsufficientHistoryError:
                skipped += 1
                break

            baseline_value = flat_baseline_forecast(truncated, horizon)

            for step, prediction in enumerate(predictions, start=1):
                target = pd.Timestamp(prediction["date"]).date()
                rows.append(
                    {
                        "step": step,
                        "actual": actual_by_date.get(target, 0.0),
                        "model": float(prediction["predicted_demand"]),
                        "baseline": baseline_value,
                    }
                )

    if not rows:
        raise RuntimeError("Backtest produced no rows; is the database populated?")

    frame = pd.DataFrame(rows)
    overall = {
        f"Moving Average ({horizon}d flat)": evaluate(frame["actual"], frame["baseline"]),
        f"ML model ({horizon}d recursive)": evaluate(frame["actual"], frame["model"]),
    }

    per_step = []
    for step, group in frame.groupby("step"):
        per_step.append(
            {
                "step": int(step),
                "baseline_wape": wape(group["actual"], group["baseline"]),
                "model_wape": wape(group["actual"], group["model"]),
                "model_mae": mae(group["actual"], group["model"]),
            }
        )

    return {
        "horizon": horizon,
        "origins": origins,
        "rows": len(frame),
        "products_skipped": skipped,
        "overall": overall,
        "per_step": per_step,
    }


def main() -> None:
    """Run horizon backtests for every supported forecast length."""
    import json

    from app.config import MODEL_DIR
    from app.database import close_pool

    reports = {}
    try:
        for horizon in (7, 14, 30):
            report = horizon_backtest(horizon=horizon, origins=6)
            reports[horizon] = report

            print(f"\n=== {horizon}-day horizon "
                  f"({report['rows']:,} predictions, {report['origins']} origins per SKU) ===")
            print(comparison_table(report["overall"]))

            if horizon == 7:
                print("\n  Error growth across the horizon:")
                print(f"  {'Step':<6}{'Baseline WAPE':>16}{'Model WAPE':>14}{'Model MAE':>12}")
                for row in report["per_step"]:
                    print(
                        f"  {row['step']:<6}{row['baseline_wape'] * 100:>15.2f}%"
                        f"{row['model_wape'] * 100:>13.2f}%{row['model_mae']:>12.2f}"
                    )

        output = MODEL_DIR / "backtest.json"
        output.write_text(json.dumps(reports, indent=2, default=float), encoding="utf-8")
        print(f"\nSaved backtest report to {output}")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
