"""Difficulty models. The data here is synthetic: labels follow a made-up rule."""

import numpy as np
import pandas as pd
import pytest

from questioniq.difficulty import (
    choose_best,
    compare_models,
    fit_final,
    save_best,
    training_labels,
)

CFG = {
    "random_state": 42,
    "difficulty": {
        "cv_folds": 3,
        "inner_folds": 2,
        "labels": ["Easy", "Medium", "Hard"],
        "rf_grid": {"n_estimators": [20], "max_depth": [None, 3]},
        "lr_grid": {"C": [0.1, 1]},
    },
}


@pytest.fixture
def data() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(42)
    bloom = rng.integers(1, 7, size=90)
    noise = rng.normal(size=90)
    X = pd.DataFrame({"bloom_level": bloom, "noise": noise}, index=[f"7-{n}" for n in range(90)])
    y = pd.Series(np.where(bloom <= 2, "Easy", np.where(bloom <= 4, "Medium", "Hard")), index=X.index)
    return X, y


def test_settled_labels_replace_round1_and_skips_are_left_out() -> None:
    round1 = {"7-1": "Easy", "7-2": "Hard", "7-3": "Skip", "9-9": "Medium"}
    labels = training_labels(round1, ["7-1", "7-2", "7-3"], {"7-2": "Medium"})
    assert labels == {"7-1": "Easy", "7-2": "Medium"}


def test_models_learn_the_rule_and_beat_the_baseline(data) -> None:
    X, y = data
    results = compare_models(X, y, CFG)
    assert set(results) == {"random_forest", "logistic_regression", "majority_baseline"}
    assert results["random_forest"]["macro_f1_mean"] > 0.9
    assert results["majority_baseline"]["macro_f1_mean"] < 0.3
    assert len(results["random_forest"]["macro_f1_folds"]) == 3
    assert sum(map(sum, results["logistic_regression"]["confusion_matrix"])) == 90  # every question predicted once
    assert choose_best(results) in {"random_forest", "logistic_regression"}


def test_nested_cv_is_repeatable(data) -> None:
    X, y = data
    first = compare_models(X, y, CFG)["random_forest"]["macro_f1_folds"]
    assert compare_models(X, y, CFG)["random_forest"]["macro_f1_folds"] == first


def test_choose_best_never_picks_the_baseline() -> None:
    results = {"random_forest": {"macro_f1_mean": 0.4}, "logistic_regression": {"macro_f1_mean": 0.5},
               "majority_baseline": {"macro_f1_mean": 0.9}}
    assert choose_best(results) == "logistic_regression"


def test_final_model_is_saved_with_its_metadata(data, tmp_path) -> None:
    X, y = data
    model = fit_final("random_forest", X, y, CFG)
    save_best(model, tmp_path / "difficulty.joblib", {"features": list(X.columns)})
    import joblib

    saved = joblib.load(tmp_path / "difficulty.joblib")
    assert saved["features"] == ["bloom_level", "noise"]
    assert set(saved["model"].predict(X.iloc[:5])) <= {"Easy", "Medium", "Hard"}
