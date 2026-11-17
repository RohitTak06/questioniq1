"""Difficulty features. All question text here is made up."""

from pathlib import Path

import pytest

from questioniq.features import (
    bloom_level,
    count_sub_parts,
    feature_names,
    feature_table,
    has_formula,
    has_numbers,
    load_bloom_verbs,
    marks_value,
    n_technical_terms,
    technical_vocabulary,
    topic_features,
    word_count,
)

VERBS = {"define": 1, "explain": 2, "solve": 3, "evaluate": 3, "analyse": 4, "prove": 5, "design": 6}
PHRASES = {"what is": 1}


def test_bloom_verb_list_file_loads_with_all_six_levels() -> None:
    verbs, phrases = load_bloom_verbs(Path(__file__).resolve().parent.parent / "bloom_verbs.yaml")
    assert set(verbs.values()) == {1, 2, 3, 4, 5, 6}
    assert verbs["design"] == 6 and verbs["define"] == 1 and verbs["evaluate"] == 3
    assert phrases["what is"] == 1


@pytest.mark.parametrize(
    "text, level",
    [
        ("Define a fake heap.", 1),
        ("Define a fake heap and design a fake scheduler.", 6),
        ("Proves that the fake set is closed", 5),
        ("Designed fake circuit", 6),
        ("What is a fake router?", 1),
        ("Fake words only", 0),
    ],
)
def test_bloom_level_is_the_highest_verb_level(text: str, level: int) -> None:
    assert bloom_level(text, VERBS, PHRASES) == level


def test_simple_text_features() -> None:
    assert word_count("Fake  question with five words") == 5
    assert count_sub_parts("Fake stem (a) part one (b) part two (ii) part three") == 3
    assert count_sub_parts("Fake e.g. no parts here") == 0
    assert has_numbers("Fake 12 items") == 1 and has_numbers("Fake none") == 0
    assert has_formula("Find x if x^2 = 4") == 1
    assert has_formula("Evaluate the integral of fake f") == 1
    assert has_formula("Explain fake routing") == 0


def test_technical_vocabulary_keeps_rare_words_seen_more_than_once() -> None:
    docs = ["fake common eigenvalue", "fake common eigenvalue", "fake common", "fake common", "fake typo"]
    technical = technical_vocabulary(docs, min_df=2)
    assert "eigenvalue" in technical and "fake" not in technical and "typo" not in technical
    assert n_technical_terms("eigenvalue eigenvalue fake", technical) == 1


def test_marks_value_and_topic_columns() -> None:
    assert marks_value("5.0") == 5.0 and marks_value("") is None and marks_value(None) is None
    assert topic_features(2, 3) == {"topic_1": 0, "topic_2": 1, "topic_3": 0}
    assert topic_features(0, 2) == {"topic_1": 0, "topic_2": 0}


def test_feature_table_fills_missing_marks_with_the_median_and_flags_them() -> None:
    rows = [
        {"question_id": "7-1", "text": "Define fake heap", "clean_text": "fake heap", "marks": "2"},
        {"question_id": "7-2", "text": "Design fake (a) x (b) y", "clean_text": "fake", "marks": "6"},
        {"question_id": "7-3", "text": "Solve 2x = 4", "clean_text": "fake", "marks": ""},
    ]
    table = feature_table(rows, {"7-1": 1, "7-2": 2}, 2, VERBS, PHRASES, {"heap"})
    assert list(table.columns) == ["question_id"] + feature_names(2)
    third = table.set_index("question_id").loc["7-3"]
    assert third["marks"] == 4.0 and third["marks_missing"] == 1
    assert third["has_formula"] == 1 and third["topic_1"] == 0 and third["topic_2"] == 0
    second = table.set_index("question_id").loc["7-2"]
    assert second["bloom_level"] == 6 and second["n_sub_parts"] == 2 and second["topic_2"] == 1
    assert table.set_index("question_id").loc["7-1", "n_technical_terms"] == 1
