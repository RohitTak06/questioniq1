"""Labelling logic. All questions and labels here are made up; none is real."""

import random
from datetime import datetime, timedelta, timezone

import pytest

from questioniq.annotate import (
    add_question_ids,
    agreement_report,
    append_label,
    department,
    draw_round1,
    draw_round2,
    first_unlabelled,
    hide_marks,
    id_order,
    labelling_pool,
    latest_labels,
    proportional_shares,
    queue_problems,
    read_rows,
    round2_opens_at,
    text_hash,
)

T0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


def question(paper: str, course: str, text: str = "fake question text here", n_tokens: int = 3) -> dict:
    return {"paper_id": paper, "course": course, "text": text, "n_tokens": str(n_tokens)}


def test_question_ids_count_within_each_paper() -> None:
    rows = add_question_ids([question("7", "XX1"), question("7", "XX1"), question("9", "XX1")])
    assert [row["question_id"] for row in rows] == ["7-1", "7-2", "9-1"]


def test_id_order_sorts_numerically() -> None:
    assert sorted(["33-10", "33-2", "9-1"], key=id_order) == ["9-1", "33-2", "33-10"]


def test_department_is_the_course_letters() -> None:
    assert department("CS1140") == "CS"
    assert department("as11114") == "AS"
    assert department("CSE1132") == "CS"  # an older code for the CS course


def test_pool_drops_empty_short_and_very_long_rows() -> None:
    rows = [
        question("1", "XX1", "fake " * 10),
        question("2", "XX1", "fake " * 10, n_tokens=0),
        question("3", "XX1", "fake fake"),
        question("4", "XX1", "fake " * 400),
    ]
    assert [row["paper_id"] for row in labelling_pool(rows, 5, 300)] == ["1"]


def test_pool_can_be_limited_to_studied_departments() -> None:
    rows = [question("1", "CS1140", "fake " * 10), question("2", "ME1103", "fake " * 10),
            question("3", "CSE1132", "fake " * 10), question("4", "AS1202", "fake " * 10)]
    assert [row["paper_id"] for row in labelling_pool(rows, 5, 300, ["CS", "AS"])] == ["1", "3", "4"]


def test_shares_add_up_and_every_group_gets_one() -> None:
    shares = proportional_shares({"CS": 300, "AS": 170, "LD": 4, "IL": 7}, 300)
    assert sum(shares.values()) == 300
    assert min(shares.values()) >= 1
    assert shares["CS"] > shares["AS"] > shares["IL"] >= shares["LD"]


def test_shares_never_exceed_a_group_and_cap_at_the_total() -> None:
    assert proportional_shares({"A": 2, "B": 1}, 10) == {"A": 2, "B": 1}


def make_pool() -> list[dict]:
    rows = [question(str(p), "CS1") for p in range(1, 41)] + [question(str(p), "AS1") for p in range(41, 61)]
    return add_question_ids(rows)


def test_round1_draw_is_repeatable_spread_and_holds_no_text() -> None:
    first = draw_round1(make_pool(), 15, random.Random(42))
    again = draw_round1(make_pool(), 15, random.Random(42))
    assert first == again
    assert len(first) == 15
    assert sum(row["course"] == "CS1" for row in first) == 10
    assert set(first[0]) == {"question_id", "paper_id", "course", "text_hash"}


def test_round2_draw_leaves_out_skips_and_ungraded() -> None:
    queue = [{"question_id": f"{n}-1"} for n in range(1, 7)]
    labels = {"1-1": "Easy", "2-1": "Skip", "3-1": "Hard", "4-1": "Medium", "5-1": "Hard"}
    drawn = draw_round2(queue, labels, 10, random.Random(42))
    assert {row["question_id"] for row in drawn} == {"1-1", "3-1", "4-1", "5-1"}
    assert len(draw_round2(queue, labels, 2, random.Random(42))) == 2


def test_labels_append_and_the_latest_wins(tmp_path) -> None:
    path = tmp_path / "labels" / "difficulty_round1.csv"
    append_label(path, "1-1", "Easy", T0)
    append_label(path, "1-1", "Hard", T0 + timedelta(minutes=1))
    rows = read_rows(path)
    assert len(rows) == 2  # history is kept
    assert latest_labels(rows) == {"1-1": "Hard"}


def test_first_unlabelled_position() -> None:
    queue = [{"question_id": "1-1"}, {"question_id": "1-2"}]
    assert first_unlabelled(queue, {"1-1": "Easy"}) == 1
    assert first_unlabelled(queue, {"1-1": "Easy", "1-2": "Skip"}) == 2


def label_rows(*items: tuple[str, str, datetime]) -> list[dict]:
    return [{"question_id": q, "label": l, "labelled_at": t.isoformat()} for q, l, t in items]


def test_round2_stays_shut_until_round1_is_complete() -> None:
    queue = [{"question_id": "1-1"}, {"question_id": "1-2"}]
    assert round2_opens_at(queue, label_rows(("1-1", "Easy", T0)), 48) is None


def test_round2_opens_48_hours_after_the_last_round1_label() -> None:
    queue = [{"question_id": "1-1"}, {"question_id": "1-2"}]
    rows = label_rows(("1-1", "Easy", T0), ("1-2", "Hard", T0 + timedelta(hours=3)))
    assert round2_opens_at(queue, rows, 48) == T0 + timedelta(hours=51)


def test_queue_problems_catch_missing_and_changed_questions() -> None:
    questions = {"1-1": {"text": "fake one"}, "1-2": {"text": "fake two, edited"}}
    queue = [
        {"question_id": "1-1", "text_hash": text_hash("fake one")},
        {"question_id": "1-2", "text_hash": text_hash("fake two")},
        {"question_id": "1-3", "text_hash": text_hash("fake three")},
    ]
    assert queue_problems(queue, questions) == ["1-2", "1-3"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Fake routing question [5]", "Fake routing question"),
        ("Fake question (5 marks) here", "Fake question here"),
        ("Fake question 2+3 Marks", "Fake question"),
        ("Fake question Marks (CO-1)", "Fake question (CO-1)"),
        ("Find f(2) for x = 10", "Find f(2) for x = 10"),
    ],
)
def test_hide_marks_removes_marks_but_not_other_numbers(text: str, expected: str) -> None:
    assert hide_marks(text) == expected


def test_perfect_agreement_gives_kappa_one() -> None:
    labels = {"1-1": "Easy", "1-2": "Medium", "1-3": "Hard"}
    report = agreement_report(labels, dict(labels))
    assert report["kappa"] == 1.0
    assert report["agreement"] == 1.0
    assert report["disagreements"] == []


def test_agreement_leaves_out_skips_and_lists_disagreements() -> None:
    first = {"1-1": "Easy", "1-2": "Hard", "1-3": "Skip", "1-4": "Medium", "1-5": "Easy"}
    second = {"1-1": "Easy", "1-2": "Medium", "1-3": "Hard", "1-4": "Medium", "1-5": "Easy"}
    report = agreement_report(first, second)
    assert report["n_compared"] == 4
    assert report["agreement"] == 0.75
    assert report["disagreements"] == [{"question_id": "1-2", "first": "Hard", "second": "Medium"}]
    assert report["confusion_matrix"] == [[2, 0, 0], [0, 1, 0], [0, 1, 0]]


def test_kappa_matches_the_textbook_value() -> None:
    # 2x2-style case on two grades: observed 0.8, expected 0.5, so Kappa = 0.6.
    first = {f"1-{n}": label for n, label in enumerate(["Easy"] * 5 + ["Hard"] * 5, start=1)}
    second = dict(first)
    second["1-1"], second["1-6"] = "Hard", "Easy"
    assert agreement_report(first, second)["kappa"] == pytest.approx(0.6)
