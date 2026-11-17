"""Explain predictions with the method that matches each model (Phase 6).

- Random Forest: SHAP values (TreeExplainer). For one question and one class, a feature's
  SHAP value is how much it moved the predicted probability of that class away from the
  average; the values for a question add up to its prediction minus the average.
- Logistic Regression: its coefficients per class, on scaled features.
- Topics: the question's main topics and which of their keywords appear in it.
Every feature value is also turned into plain English for the dashboard.
"""

from typing import Any

import numpy as np
import pandas as pd
import shap

BLOOM_NAMES = {0: "no command verb found", 1: "Remember", 2: "Understand", 3: "Apply",
               4: "Analyse", 5: "Evaluate", 6: "Create"}


def class_shap_values(model: Any, X: pd.DataFrame) -> dict[str, np.ndarray]:
    """Return SHAP values for every class: {class: array of shape (questions, features)}.

    Different SHAP versions return one array with a class axis or a list per class;
    both are turned into the same form here.
    """
    values = shap.TreeExplainer(model).shap_values(X)
    if isinstance(values, list):
        return {str(label): np.asarray(part) for label, part in zip(model.classes_, values)}
    values = np.asarray(values)
    return {str(label): values[:, :, index] for index, label in enumerate(model.classes_)}


def describe_feature(name: str, value: float, topic_names: dict[int, str] | None = None) -> str:
    """Return a feature's value in plain English, such as "10 marks" or "contains a formula"."""
    value = float(value)
    topic_names = topic_names or {}
    if name == "bloom_level":
        level = int(value)
        return f"Bloom level {level} ({BLOOM_NAMES[level]})" if level else BLOOM_NAMES[0]
    if name == "word_count":
        return f"{int(value)} words"
    if name == "marks":
        return f"{value:g} marks"
    if name == "marks_missing":
        return "marks not found" if value else "marks found"
    if name == "n_sub_parts":
        return "no labelled parts" if value == 0 else f"{int(value)} part{'s' if value != 1 else ''}"
    if name == "has_numbers":
        return "contains numbers" if value else "no numbers"
    if name == "has_formula":
        return "contains a formula" if value else "no formula"
    if name == "n_technical_terms":
        return f"{int(value)} technical word{'s' if value != 1 else ''}"
    if name.startswith("topic_"):
        number = int(name.split("_")[1])
        topic = topic_names.get(number, f"Topic {number}")
        return f"topic: {topic}" if value else f"not about {topic}"
    return f"{name} = {value:g}"


def shap_top_features(
    shap_row: np.ndarray, values: pd.Series, n: int = 5, topic_names: dict[int, str] | None = None
) -> list[dict]:
    """Return the n strongest signed SHAP features for one question and one class.

    Strongest means largest absolute SHAP value. A positive value pushed the question
    towards the class, a negative one away from it.
    """
    order = np.argsort(np.abs(shap_row))[::-1][:n]
    return [
        {
            "feature": values.index[i],
            "value": float(values.iloc[i]),
            "shap": round(float(shap_row[i]), 4),
            "text": describe_feature(values.index[i], values.iloc[i], topic_names),
        }
        for i in order
    ]


def because_sentence(predicted: str, reasons: list[dict], n: int = 3) -> str:
    """Return a one-line reason, such as "Hard because: Bloom level 5 (Evaluate), 10 marks".

    Only features that pushed towards the predicted class are named.
    """
    pushing = [reason["text"] for reason in reasons if reason["shap"] > 0][:n]
    if not pushing:
        return f"{predicted}: no single feature stands out"
    return f"{predicted} because: {', '.join(pushing)}"


def explain_rows(model: Any, X: pd.DataFrame, n: int = 5, topic_names: dict[int, str] | None = None) -> list[dict]:
    """Return each question's prediction, class probabilities and top SHAP reasons."""
    by_class = class_shap_values(model, X)
    probabilities = model.predict_proba(X)
    explanations = []
    for row_index, (question_id, values) in enumerate(X.iterrows()):
        shares = {str(label): round(float(p), 3) for label, p in zip(model.classes_, probabilities[row_index])}
        predicted = max(shares, key=shares.get)
        reasons = shap_top_features(by_class[predicted][row_index], values, n, topic_names)
        explanations.append({
            "question_id": question_id,
            "predicted": predicted,
            "probabilities": shares,
            "reasons": reasons,
            "because": because_sentence(predicted, reasons),
        })
    return explanations


def global_importance(by_class: dict[str, np.ndarray], feature_names: list[str]) -> dict[str, float]:
    """Return each feature's mean absolute SHAP value over all questions and classes, largest first."""
    stacked = np.mean([np.abs(values).mean(axis=0) for values in by_class.values()], axis=0)
    ranked = sorted(zip(feature_names, stacked), key=lambda item: -item[1])
    return {name: round(float(value), 4) for name, value in ranked}


def lr_coefficients(model: Any, feature_names: list[str]) -> dict[str, list[dict]]:
    """Return Logistic Regression coefficients per class, mapped to feature names.

    The model scales features first, so coefficients can be compared: a large positive
    coefficient means more of that feature pulls a question towards the class.
    Sorted by absolute size.
    """
    estimator = model.named_steps["model"] if hasattr(model, "named_steps") else model
    result = {}
    for label, coefficients in zip(estimator.classes_, estimator.coef_):
        pairs = sorted(zip(feature_names, coefficients), key=lambda item: -abs(item[1]))
        result[str(label)] = [{"feature": name, "coefficient": round(float(value), 4)} for name, value in pairs]
    return result


def topic_explanation(
    tokens: list[str],
    distribution: list[float],
    keywords: list[list[str]],
    topic_names: dict[int, str] | None = None,
    n_topics: int = 3,
) -> dict:
    """Return a question's topic distribution and the topic keywords that appear in it.

    Topics are numbered from 1. Only topics with a share above zero are listed, largest
    first, each with the keywords (or word pairs) found in the question's cleaned text.
    """
    topic_names = topic_names or {}
    present = set(tokens) | {f"{a}_{b}" for a, b in zip(tokens, tokens[1:])}
    order = [i for i in np.argsort(distribution)[::-1] if distribution[i] > 0][:n_topics]
    return {
        "topics": [
            {
                "topic": int(i) + 1,
                "name": topic_names.get(int(i) + 1, f"Topic {int(i) + 1}"),
                "share": round(float(distribution[i]), 3),
                "keywords_found": [word for word in keywords[i] if word in present],
            }
            for i in order
        ]
    }
