"""Training pipeline tests.

These run the real trainer against whatever is in the database, so they are the
end-to-end check that the pipeline holds together. They assert structure and
sanity rather than specific accuracy numbers — pinning a WAPE value would make
the suite fail every time the data or model is tuned.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.evaluate import evaluate
from app.ml.feature_engineering import FEATURE_COLUMNS, TARGET_COLUMN
from app.ml.train_model import candidate_models, load_dataset, predict_clipped, train
from app.models import product as product_model


@pytest.fixture(scope="module")
def dataset():
    if not product_model.list_products(limit=1):
        pytest.skip("database is empty; run scripts/load_data.py")
    return load_dataset()


@pytest.fixture(scope="module")
def report(dataset):
    # save=False keeps the test run from overwriting the committed model.
    return train(save=False)


def test_dataset_contains_every_declared_feature(dataset):
    assert set(FEATURE_COLUMNS) <= set(dataset.columns)
    assert TARGET_COLUMN in dataset.columns


def test_dataset_has_no_missing_feature_values(dataset):
    assert not dataset[FEATURE_COLUMNS].isna().any().any()


def test_dataset_is_sorted_by_date(dataset):
    assert dataset["sale_date"].is_monotonic_increasing


def test_dataset_spans_multiple_products(dataset):
    assert dataset["product_id"].nunique() > 1


def test_training_splits_are_chronological(report):
    train_range = report["date_ranges"]["train"]
    validation_range = report["date_ranges"]["validation"]
    test_range = report["date_ranges"]["test"]

    assert train_range[1] < validation_range[0]
    assert validation_range[1] < test_range[0]


def test_split_sizes_are_roughly_70_15_15(report):
    rows = report["rows"]
    total = rows["total"]
    assert rows["train"] / total == pytest.approx(0.70, abs=0.05)
    assert rows["validation"] / total == pytest.approx(0.15, abs=0.05)
    assert rows["test"] / total == pytest.approx(0.15, abs=0.05)


def test_selected_model_is_one_of_the_candidates(report):
    assert report["selected_model"] in candidate_models()


def test_report_contains_all_three_metrics(report):
    for scores in report["test_scores"].values():
        assert {"mae", "rmse", "wape"} == set(scores)
        assert all(np.isfinite(value) for value in scores.values())


def test_model_beats_the_moving_average_baseline(report):
    """The whole point of the ML model. If this fails, ship the baseline."""
    baseline = report["test_scores"]["Moving Average (7d)"]
    model = report["test_scores"][report["selected_model"]]

    assert model["wape"] < baseline["wape"]
    assert model["mae"] < baseline["mae"]


def test_predictions_are_never_negative(dataset):
    model = candidate_models()["Random Forest"]
    sample = dataset.tail(500)
    model.fit(sample[FEATURE_COLUMNS], sample[TARGET_COLUMN])
    assert (predict_clipped(model, sample[FEATURE_COLUMNS]) >= 0).all()


def test_metrics_are_computed_on_the_held_out_window(report):
    """Test scores should be no better than validation scores by a wide margin."""
    selected = report["selected_model"]
    validation_wape = report["validation_scores"][selected]["wape"]
    test_wape = report["test_scores"][selected]["wape"]
    assert evaluate([1, 2], [1, 2])["wape"] == 0.0
    assert abs(test_wape - validation_wape) < 0.15
