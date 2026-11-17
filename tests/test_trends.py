"""Trend tables on a small made-up set of questions."""

import pandas as pd

from questioniq.trends import difficulty_mix_by_year, recurring_concepts, topic_share_by_year


def test_topic_share_is_per_year_and_exam_type_and_skips_no_topic() -> None:
    df = pd.DataFrame({"year": [2023, 2023, 2023, 2024, 2024],
                       "exam_type": ["Endterm"] * 5, "dominant_topic": [1, 1, 2, 2, 0]})
    table = topic_share_by_year(df)
    first = table[(table.year == 2023) & (table.topic == 1)].iloc[0]
    assert (first.n_questions, first.year_total, first.share) == (2, 3, 0.667)
    assert table[table.year == 2024].iloc[0].year_total == 1  # the question without a topic is left out


def test_difficulty_mix_shares_add_to_one_and_keep_the_count() -> None:
    df = pd.DataFrame({"year": [2023, 2023, 2023, 2023, 2024],
                       "difficulty": ["Easy", "Hard", "Hard", "Skip", "Medium"]})
    table = difficulty_mix_by_year(df).set_index("year")
    assert table.loc[2023, "n_questions"] == 3
    assert (table.loc[2023, "Easy"], table.loc[2023, "Medium"], table.loc[2023, "Hard"]) == (0.333, 0.0, 0.667)
    assert table.loc[2024, "Medium"] == 1.0


def test_recurring_concepts_need_enough_different_years() -> None:
    df = pd.DataFrame({"year": [2020, 2022, 2023, 2023, 2024],
                       "concepts": [["binary_tree"], ["binary_tree", "heap"], ["heap"], ["binary_tree"], []]})
    table = recurring_concepts(df, min_years=3)
    assert table.to_dict("records") == [
        {"concept": "binary_tree", "n_years": 3, "years": "2020, 2022, 2023", "n_questions": 3}
    ]
    assert len(recurring_concepts(df, min_years=2)) == 2
