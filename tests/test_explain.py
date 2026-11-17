"""Explanations. The model here is trained on synthetic data with a made-up rule."""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from questioniq.explain import (
    because_sentence,
    class_shap_values,
    describe_feature,
    explain_rows,
    global_importance,
    lr_coefficients,
    shap_top_features,
    topic_explanation,
)


@pytest.fixture(scope="module")
def data() -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(42)
    bloom = rng.integers(1, 7, size=120)
    X = pd.DataFrame({"bloom_level": bloom, "word_count": rng.integers(5, 80, size=120),
                      "has_formula": rng.integers(0, 2, size=120)},
                     index=[f"7-{n}" for n in range(120)])
    y = pd.Series(np.where(bloom <= 2, "Easy", np.where(bloom <= 4, "Medium", "Hard")), index=X.index)
    return X, y


@pytest.fixture(scope="module")
def forest(data) -> RandomForestClassifier:
    X, y = data
    return RandomForestClassifier(n_estimators=50, random_state=42).fit(X, y)


def test_shap_values_per_class_add_up_to_the_prediction(forest, data) -> None:
    X, _ = data
    by_class = class_shap_values(forest, X.iloc[:10])
    assert set(by_class) == {"Easy", "Hard", "Medium"}
    assert by_class["Hard"].shape == (10, 3)
    # SHAP's promise: average prediction + the question's SHAP values = its prediction
    import shap

    base = shap.TreeExplainer(forest).expected_value
    hard = list(forest.classes_).index("Hard")
    probability = forest.predict_proba(X.iloc[:10])[:, hard]
    assert np.allclose(np.ravel(base)[hard] + by_class["Hard"].sum(axis=1), probability, atol=1e-6)


def test_bloom_is_the_main_reason_for_the_rule_it_follows(forest, data) -> None:
    X, _ = data
    explanation = explain_rows(forest, X.iloc[:5])[0]
    assert explanation["reasons"][0]["feature"] == "bloom_level"
    assert explanation["predicted"] in {"Easy", "Medium", "Hard"}
    assert abs(sum(explanation["probabilities"].values()) - 1) < 1e-6


def test_top_features_are_ordered_by_strength_and_keep_their_sign() -> None:
    values = pd.Series({"bloom_level": 5, "marks": 10, "has_formula": 1})
    reasons = shap_top_features(np.array([0.02, -0.10, 0.05]), values, n=2)
    assert [(r["feature"], r["shap"]) for r in reasons] == [("marks", -0.1), ("has_formula", 0.05)]
    assert reasons[1]["text"] == "contains a formula"


def test_because_sentence_names_only_features_pushing_towards_the_class() -> None:
    reasons = [{"text": "10 marks", "shap": -0.1}, {"text": "contains a formula", "shap": 0.05},
               {"text": "Bloom level 5 (Evaluate)", "shap": 0.03}]
    assert because_sentence("Hard", reasons) == "Hard because: contains a formula, Bloom level 5 (Evaluate)"
    assert "stands out" in because_sentence("Easy", reasons[:1])


@pytest.mark.parametrize(
    "name, value, text",
    [
        ("bloom_level", 6, "Bloom level 6 (Create)"),
        ("bloom_level", 0, "no command verb found"),
        ("marks", 2.5, "2.5 marks"),
        ("marks_missing", 1, "marks not found"),
        ("n_sub_parts", 1, "1 part"),
        ("n_sub_parts", 3, "3 parts"),
        ("has_numbers", 0, "no numbers"),
        ("n_technical_terms", 2, "2 technical words"),
        ("topic_5", 1, "topic: Fake trees"),
        ("topic_2", 0, "not about Topic 2"),
    ],
)
def test_features_read_as_plain_english(name: str, value: float, text: str) -> None:
    assert describe_feature(name, value, {5: "Fake trees"}) == text


def test_global_importance_ranks_features() -> None:
    by_class = {"Easy": np.array([[0.3, 0.0], [0.1, 0.0]]), "Hard": np.array([[0.1, 0.2], [0.1, 0.0]])}
    assert list(global_importance(by_class, ["bloom_level", "marks"])) == ["bloom_level", "marks"]


def test_lr_coefficients_are_mapped_to_names_per_class(data) -> None:
    X, y = data
    model = Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(max_iter=2000))]).fit(X, y)
    coefficients = lr_coefficients(model, list(X.columns))
    assert set(coefficients) == {"Easy", "Hard", "Medium"}
    assert coefficients["Hard"][0]["feature"] == "bloom_level" and coefficients["Hard"][0]["coefficient"] > 0
    assert coefficients["Easy"][0]["feature"] == "bloom_level" and coefficients["Easy"][0]["coefficient"] < 0


def test_topic_explanation_lists_main_topics_and_keywords_found() -> None:
    keywords = [["tree", "binary_tree", "node"], ["matrix", "rank"], ["router"]]
    result = topic_explanation(["fake", "binary", "tree", "node"], [0.7, 0.3, 0.0], keywords, {1: "Fake trees"})
    assert result["topics"] == [
        {"topic": 1, "name": "Fake trees", "share": 0.7, "keywords_found": ["tree", "binary_tree", "node"]},
        {"topic": 2, "name": "Topic 2", "share": 0.3, "keywords_found": []},
    ]


def test_explanation_check_score_and_target() -> None:
    from scripts.explain_eval import score_explanations

    rows = [{"review_no": str(n), "question_id": f"7-{n}", "matches_rubric": "yes", "notes": ""} for n in range(1, 4)]
    rows.append({"review_no": "4", "question_id": "7-4", "matches_rubric": "No", "notes": "fake"})
    report = score_explanations(rows, target=3)
    assert (report["n_yes"], report["n_checked"], report["passes"]) == (3, 4, True)
    assert report["no"] == [{"review_no": "4", "question_id": "7-4", "notes": "fake"}]
    rows[0]["matches_rubric"] = ""
    assert score_explanations(rows, target=2)["passes"] is False  # not every row answered yet


def test_topic_names_only_use_filled_in_names() -> None:
    from scripts.run_explain import topic_names_from

    rows = [{"topic": "1", "name": " Fake trees "}, {"topic": "2", "name": ""}]
    assert topic_names_from(rows) == {1: "Fake trees"}
