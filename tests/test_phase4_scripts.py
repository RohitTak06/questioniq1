"""The Kappa script's outputs. All labels and questions here are fake."""

from scripts.kappa import disagreements_markdown, settle_rows

REPORT = {"disagreements": [{"question_id": "7-2", "first": "Hard", "second": "Medium"}]}


def test_settle_sheet_has_one_blank_row_per_disagreement() -> None:
    assert settle_rows(REPORT) == [{"question_id": "7-2", "round1": "Hard", "round2": "Medium"}]


def test_disagreement_list_shows_both_labels_and_the_text() -> None:
    text = disagreements_markdown(REPORT, {"7-2": {"course": "XX1", "text": "Fake question"}}, "fake.csv")
    assert "7-2 (XX1): round 1 Hard, round 2 Medium" in text
    assert "Fake question" in text
    assert "fake.csv" in text


def test_disagreement_list_survives_a_missing_question() -> None:
    assert "(question not found)" in disagreements_markdown(REPORT, {}, "fake.csv")
