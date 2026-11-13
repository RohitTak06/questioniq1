"""The preprocessing script's report and sampling logic. All data here is fake."""

import random

from scripts.run_preprocess import (
    add_clean_text,
    check_rows,
    document_frequency,
    review_markdown,
    review_sample,
    summary_markdown,
)


def row(number: int, text: str) -> dict:
    return {
        "paper_id": str(number),
        "course": "XX1",
        "qno": "1",
        "sub_part": "",
        "alternative": "0",
        "text": text,
    }


ROWS = add_clean_text(
    [row(1, "Explain fake routing tables"), row(2, "Fake routing protocols"), row(3, "| 12 |")],
    {"explain"},
    3,
)


def test_clean_text_is_added_and_raw_text_kept() -> None:
    assert ROWS[0]["text"] == "Explain fake routing tables"
    assert ROWS[0]["clean_text"] == "fake routing table"
    assert ROWS[0]["n_tokens"] == 3


def test_document_frequency_counts_questions_not_repeats() -> None:
    rows = add_clean_text([row(1, "fake fake routing")], set(), 3)
    assert document_frequency(rows) == {"fake": 1, "routing": 1}


def test_summary_reports_empty_questions_and_min_df_vocabulary() -> None:
    text = summary_markdown(ROWS, min_df=2)
    assert "- Questions left empty after cleaning: 1" in text
    assert "4 words, 2 in at least 2 questions" in text
    assert "| routing | 2 |" in text


def test_review_sample_skips_empty_questions_and_is_repeatable() -> None:
    first = review_sample(ROWS, 5, random.Random(42))
    again = review_sample(ROWS, 5, random.Random(42))
    assert first == again
    assert {r["paper_id"] for r in first} == {"1", "2"}


def test_review_shows_raw_and_clean_and_names_the_sheet() -> None:
    text = review_markdown(ROWS[:1], "data/fake_check.csv")
    assert "**Raw:** Explain fake routing tables" in text
    assert "**Clean:** fake routing table" in text
    assert "data/fake_check.csv" in text


def test_check_rows_are_blank_for_the_owner() -> None:
    sheet = check_rows(ROWS[:1])
    assert sheet == [{"review_no": 1, "paper_id": "1", "qno": "1", "sub_part": "", "alternative": "0"}]
