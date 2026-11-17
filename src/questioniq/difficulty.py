"""Train and compare the Easy/Medium/Hard classifiers (Phase 5).

Random Forest and Logistic Regression are compared with a majority-class baseline using
nested cross-validation: stratified 5-fold CV on the outside, and the grid search runs only
inside each outer training part. The outer test fold is never seen while choosing settings,
so the scores are not flattered by the search.
"""

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from questioniq.annotate import GRADES, latest_labels, read_rows


def training_labels(round1: dict[str, str], queue_ids: list[str], settled: dict[str, str]) -> dict[str, str]:
    """Return the label to train on for each graded round-1 question.

    Round 1 is the base. Where the owner settled a round-1/round-2 disagreement, the
    settled label replaces it. Skips and questions outside the queue are left out.
    """
    labels = {}
    for question_id in queue_ids:
        label = settled.get(question_id) or round1.get(question_id)
        if label in GRADES:
            labels[question_id] = label
    return labels


def load_training_labels(paths: dict) -> tuple[dict[str, str], str]:
    """Read the owner's labels from disk and return them with a note on where they came from.

    Uses round 1 for the round-1 queue, replaced by settled labels where the owner
    filled in final_label after round 2.
    """
    labels_dir = Path(paths["labels"])
    round1 = latest_labels(read_rows(labels_dir / "difficulty_round1.csv"))
    queue_ids = [row["question_id"] for row in read_rows(Path(paths["round1_queue"]))]
    settled = {row["question_id"]: row["final_label"].strip()
               for row in read_rows(Path(paths["settle_sheet"])) if row.get("final_label", "").strip()}
    source = "round 1" + (f", with {len(settled)} settled after round 2" if settled else " (round 2 not settled yet)")
    return training_labels(round1, queue_ids, settled), source


def candidate_models(cfg: dict) -> dict[str, tuple[Any, dict]]:
    """Return each model with its search grid: RF, scaled LR, and the majority baseline."""
    settings = cfg["difficulty"]
    random_state = cfg["random_state"]
    forest = RandomForestClassifier(class_weight="balanced", random_state=random_state)
    logistic = Pipeline([
        ("scale", StandardScaler()),
        ("model", LogisticRegression(class_weight="balanced", max_iter=5000, random_state=random_state)),
    ])
    return {
        "random_forest": (forest, settings["rf_grid"]),
        "logistic_regression": (logistic, {f"model__{key}": values for key, values in settings["lr_grid"].items()}),
        "majority_baseline": (DummyClassifier(strategy="most_frequent"), {}),
    }


def _search(model: Any, grid: dict, folds: int, random_state: int) -> Any:
    """Wrap a model in a grid search on macro-F1, or return it as is when there is no grid."""
    if not grid:
        return clone(model)
    inner = StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_state)
    return GridSearchCV(clone(model), grid, scoring="f1_macro", cv=inner)


def nested_cv(model: Any, grid: dict, X: pd.DataFrame, y: pd.Series, cfg: dict) -> dict:
    """Score one model with nested CV and return its fold scores and pooled predictions.

    Each question is predicted exactly once, by a model that never saw it while it was
    trained or tuned. Per-class scores and the confusion matrix use those predictions.
    """
    settings = cfg["difficulty"]
    random_state = cfg["random_state"]
    labels = settings["labels"]
    outer = StratifiedKFold(n_splits=settings["cv_folds"], shuffle=True, random_state=random_state)
    predicted = pd.Series(index=y.index, dtype=object)
    fold_scores, fold_params = [], []
    for train, test in outer.split(X, y):
        search = _search(model, grid, settings["inner_folds"], random_state)
        search.fit(X.iloc[train], y.iloc[train])
        guesses = search.predict(X.iloc[test])
        predicted.iloc[test] = guesses
        fold_scores.append(float(f1_score(y.iloc[test], guesses, labels=labels, average="macro", zero_division=0)))
        fold_params.append(getattr(search, "best_params_", {}))
    report = classification_report(y, predicted, labels=labels, output_dict=True, zero_division=0)
    return {
        "macro_f1_mean": float(np.mean(fold_scores)),
        "macro_f1_std": float(np.std(fold_scores)),
        "macro_f1_folds": fold_scores,
        "per_class": {label: {key: round(report[label][key], 3) for key in ("precision", "recall", "f1-score", "support")}
                      for label in labels},
        "accuracy": round(float(report["accuracy"]), 3),
        "labels": labels,
        "confusion_matrix": confusion_matrix(y, predicted, labels=labels).tolist(),
        "best_params_per_fold": fold_params,
    }


def compare_models(X: pd.DataFrame, y: pd.Series, cfg: dict) -> dict:
    """Compare Random Forest, Logistic Regression and a majority baseline with stratified CV."""
    return {name: nested_cv(model, grid, X, y, cfg) for name, (model, grid) in candidate_models(cfg).items()}


def choose_best(results: dict) -> str:
    """Return the trained model (not the baseline) with the higher mean macro-F1."""
    trained = {name: result for name, result in results.items() if name != "majority_baseline"}
    return max(trained, key=lambda name: trained[name]["macro_f1_mean"])


def fit_final(name: str, X: pd.DataFrame, y: pd.Series, cfg: dict) -> Any:
    """Tune the chosen model on all labelled questions and return the fitted model.

    The grid search uses the same number of folds as the outer CV, on all the data;
    the nested-CV scores above, not this fit, are the ones reported.
    """
    model, grid = candidate_models(cfg)[name]
    search = _search(model, grid, cfg["difficulty"]["cv_folds"], cfg["random_state"])
    search.fit(X, y)
    return getattr(search, "best_estimator_", search)


def save_best(model: Any, path: Path, metadata: dict | None = None) -> None:
    """Save the chosen model with joblib, together with what's needed to use it again."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, **(metadata or {})}, path)
