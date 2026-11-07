"""Explain predictions with the method that matches each model (Phase 6)."""

from typing import Any

import pandas as pd


def shap_top_features(model: Any, x: pd.DataFrame, n: int = 5) -> list[dict]:
    """Return the n strongest signed SHAP features for a Random Forest prediction."""
    raise NotImplementedError


def lr_coefficients(model: Any, feature_names: list[str]) -> dict[str, list[dict]]:
    """Return Logistic Regression coefficients per class, mapped to feature names."""
    raise NotImplementedError


def topic_explanation(
    tokens: list[str], distribution: list[float], keywords: list[list[str]]
) -> dict:
    """Return a question's topic distribution and the topic keywords that appear in it."""
    raise NotImplementedError
