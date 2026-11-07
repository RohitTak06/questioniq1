"""Train and compare the Easy/Medium/Hard classifiers (Phase 5)."""

from pathlib import Path
from typing import Any

import pandas as pd


def compare_models(X: pd.DataFrame, y: pd.Series, cfg: dict) -> dict:
    """Compare Random Forest, Logistic Regression and a majority baseline with stratified CV."""
    raise NotImplementedError


def save_best(model: Any, path: Path) -> None:
    """Save the chosen model with joblib."""
    raise NotImplementedError
