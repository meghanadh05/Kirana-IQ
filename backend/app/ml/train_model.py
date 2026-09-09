"""Train the demand forecasting model.

Run directly:

    python -m app.ml.train_model            # from the backend/ directory

The script pulls every product's history from PostgreSQL, builds features,
splits chronologically, trains two scikit-learn candidates, picks the winner on
the validation window, and reports honest test-set numbers against a 7-day
moving-average baseline.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

from app.config import MODEL_DIR

from app.ml import evaluate as metrics
from app.ml.feature_engineering import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    build_training_frame,
    chronological_split,
    load_events,
)
from app.models import product as product_model
from app.models import sale as sale_model

logger = logging.getLogger(__name__)

MODEL_PATH = MODEL_DIR / "demand_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"


def candidate_models() -> dict[str, Any]:
    """The two candidates, both with fixed seeds so runs are reproducible."""
    return {
        "Random Forest": RandomForestRegressor(
            n_estimators=300,
            max_depth=14,
            min_samples_leaf=3,
            n_jobs=-1,
            random_state=42,
        ),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            max_iter=400,
            learning_rate=0.06,
            max_depth=8,
            min_samples_leaf=20,
            l2_regularization=1.0,
            early_stopping=True,
            validation_fraction=0.1,
            random_state=42,
        ),
    }


def load_dataset() -> pd.DataFrame:
    """Build the full feature matrix from what is currently in the database."""
    products = product_model.list_products(limit=1000)
    if not products:
        raise RuntimeError("No products in the database. Run scripts/load_data.py first.")

    histories = {p["id"]: sale_model.daily_history(p["id"]) for p in products}
    events = load_events()

    frame = build_training_frame(products, histories, events=events)
    if frame.empty:
        raise RuntimeError("No usable training rows. Products need at least 31 days of history.")
    return frame


def predict_clipped(model: Any, features: pd.DataFrame) -> np.ndarray:
    """Predict and clip at zero — negative demand is not a thing."""
    return np.clip(model.predict(features), 0, None)


def train(save: bool = True) -> dict[str, Any]:
    """Train, select and persist the demand model. Returns a metrics report."""
    frame = load_dataset()
    train_set, validation_set, test_set = chronological_split(frame)

    logger.info(
        "Rows: %d train / %d validation / %d test",
        len(train_set),
        len(validation_set),
        len(test_set),
    )

    x_train = train_set[FEATURE_COLUMNS]
    y_train = train_set[TARGET_COLUMN]
    x_validation = validation_set[FEATURE_COLUMNS]
    y_validation = validation_set[TARGET_COLUMN]
    x_test = test_set[FEATURE_COLUMNS]
    y_test = test_set[TARGET_COLUMN]

    # Baseline: yesterday's 7-day mean, on the same rows the models see.
    baseline_validation = metrics.evaluate(
        y_validation, metrics.moving_average_baseline(validation_set)
    )
    baseline_test = metrics.evaluate(y_test, metrics.moving_average_baseline(test_set))

    validation_scores: dict[str, dict[str, float]] = {"Moving Average (7d)": baseline_validation}
    trained: dict[str, Any] = {}

    for name, model in candidate_models().items():
        logger.info("Training %s", name)
        model.fit(x_train, y_train)
        trained[name] = model
        validation_scores[name] = metrics.evaluate(
            y_validation, predict_clipped(model, x_validation)
        )

    # Selection happens on validation only; the test window stays untouched
    # until the winner is fixed.
    model_names = [n for n in validation_scores if n != "Moving Average (7d)"]
    best_name = min(model_names, key=lambda n: validation_scores[n]["wape"])
    best_model = trained[best_name]

    test_scores = {
        "Moving Average (7d)": baseline_test,
        best_name: metrics.evaluate(y_test, predict_clipped(best_model, x_test)),
    }

    baseline_wape = baseline_test["wape"]
    model_wape = test_scores[best_name]["wape"]
    improvement = (baseline_wape - model_wape) / baseline_wape * 100 if baseline_wape else 0.0

    report: dict[str, Any] = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "selected_model": best_name,
        "rows": {
            "total": len(frame),
            "train": len(train_set),
            "validation": len(validation_set),
            "test": len(test_set),
        },
        "date_ranges": {
            "train": [str(train_set["sale_date"].min().date()), str(train_set["sale_date"].max().date())],
            "validation": [
                str(validation_set["sale_date"].min().date()),
                str(validation_set["sale_date"].max().date()),
            ],
            "test": [str(test_set["sale_date"].min().date()), str(test_set["sale_date"].max().date())],
        },
        "validation_scores": validation_scores,
        "test_scores": test_scores,
        "wape_improvement_over_baseline_pct": improvement,
        "products": int(frame["product_id"].nunique()),
    }

    if save:
        # The served model is refit on train+validation+test so it benefits from
        # the most recent weeks. Reported metrics still come from the model that
        # never saw the test window.
        final_model = candidate_models()[best_name]
        final_model.fit(frame[FEATURE_COLUMNS], frame[TARGET_COLUMN])

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": final_model,
                "feature_columns": FEATURE_COLUMNS,
                "model_name": best_name,
                "trained_at": report["trained_at"],
                "metrics": test_scores,
            },
            MODEL_PATH,
        )
        METRICS_PATH.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
        logger.info("Saved model to %s", MODEL_PATH)

    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    report = train()

    print("\nRows      :", report["rows"])
    print("Train     :", " -> ".join(report["date_ranges"]["train"]))
    print("Validation:", " -> ".join(report["date_ranges"]["validation"]))
    print("Test      :", " -> ".join(report["date_ranges"]["test"]))

    print("\n--- Validation (model selection) ---")
    print(metrics.comparison_table(report["validation_scores"]))

    print("\n--- Test (held out) ---")
    print(metrics.comparison_table(report["test_scores"]))

    print(f"\nSelected: {report['selected_model']}")
    print(f"WAPE improvement over baseline: {report['wape_improvement_over_baseline_pct']:.1f}%")


if __name__ == "__main__":
    from app.database import close_pool

    try:
        main()
    finally:
        close_pool()
