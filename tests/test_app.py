"""The labelling page, driven through Flask's test client on fake questions."""

import csv
from datetime import datetime, timedelta, timezone

import pytest

import app.routes as routes
from app import create_app
from questioniq.annotate import QUEUE_COLUMNS, read_rows, text_hash, write_rows

COLUMNS = ["paper_id", "course", "year", "exam_type", "qno", "sub_part", "alternative", "marks", "co",
           "text", "clean_text", "n_tokens"]
TEXTS = ["Fake routing question one [5]", "Fake sorting question two", "Fake matrix question three"]
T0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def setup(tmp_path):
    questions = tmp_path / "questions_clean.csv"
    with open(questions, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for n, text in enumerate(TEXTS, start=1):
            writer.writerow({"paper_id": "7", "course": "XX1", "year": "2024", "exam_type": "Endterm",
                             "qno": str(n), "sub_part": "", "alternative": "0", "marks": "5", "co": "",
                             "text": text, "clean_text": "fake", "n_tokens": "1"})
    cfg = {
        "random_state": 42,
        "paths": {
            "labels": str(tmp_path / "labels"),
            "questions_clean": str(questions),
            "rubric": str(tmp_path / "rubric.md"),
            "round1_queue": str(tmp_path / "labels" / "round1_queue.csv"),
            "round2_queue": str(tmp_path / "labels" / "round2_queue.csv"),
            "manifest": str(tmp_path / "manifest.csv"),
        },
        "annotation": {"relabel_n": 2, "relabel_delay_hours": 48, "show_marks": False,
                       "choices": ["Easy", "Medium", "Hard", "Skip"]},
    }
    (tmp_path / "rubric.md").write_text("Fake rubric: Easy is recall.", encoding="utf-8")
    (tmp_path / "fake.pdf").write_bytes(b"%PDF-1.4 fake")
    write_rows(tmp_path / "manifest.csv", [{"paper_id": "7", "path": str(tmp_path / "fake.pdf")}], ["paper_id", "path"])
    queue = [{"question_id": f"7-{n}", "paper_id": "7", "course": "XX1", "text_hash": text_hash(text)}
             for n, text in enumerate(TEXTS, start=1)]
    write_rows(tmp_path / "labels" / "round1_queue.csv", queue, QUEUE_COLUMNS)
    client = create_app(cfg).test_client()
    return client, tmp_path


def label(client, annotator: str, question_id: str, choice: str):
    return client.post("/annotate", data={"annotator": annotator, "question_id": question_id, "label": choice})


def test_page_needs_the_rubric(setup) -> None:
    client, tmp_path = setup
    (tmp_path / "rubric.md").unlink()
    assert "Write the rubric first" in client.get("/annotate?annotator=round1").get_data(as_text=True)


def test_page_needs_the_queue(setup) -> None:
    client, tmp_path = setup
    (tmp_path / "labels" / "round1_queue.csv").unlink()
    assert "make_label_queue.py" in client.get("/annotate?annotator=round1").get_data(as_text=True)


def test_unknown_annotator_is_refused(setup) -> None:
    client, _ = setup
    assert client.get("/annotate?annotator=someone").status_code == 400


def test_first_question_shows_with_rubric_and_marks_hidden(setup) -> None:
    client, _ = setup
    page = client.get("/annotate?annotator=round1").get_data(as_text=True)
    assert "Fake routing question one" in page
    assert "[5]" not in page
    assert "Fake rubric" in page
    assert "Question 1 of 3" in page


def test_label_is_saved_and_the_next_question_follows(setup) -> None:
    client, tmp_path = setup
    response = label(client, "round1", "7-1", "Hard")
    assert response.status_code == 302 and "i=1" in response.headers["Location"]
    rows = read_rows(tmp_path / "labels" / "difficulty_round1.csv")
    assert [(row["question_id"], row["label"]) for row in rows] == [("7-1", "Hard")]
    assert "Fake sorting question two" in client.get("/annotate?annotator=round1").get_data(as_text=True)


def test_bad_label_or_question_is_refused(setup) -> None:
    client, _ = setup
    assert label(client, "round1", "7-1", "VeryHard").status_code == 400
    assert label(client, "round1", "9-9", "Easy").status_code == 400


def test_going_back_shows_your_own_label(setup) -> None:
    client, _ = setup
    label(client, "round1", "7-1", "Medium")
    page = client.get("/annotate?annotator=round1&i=0").get_data(as_text=True)
    assert "Your label in this round: Medium" in page


def test_changed_question_text_stops_the_page(setup) -> None:
    client, tmp_path = setup
    path = tmp_path / "questions_clean.csv"
    path.write_text(path.read_text(encoding="utf-8").replace("two", "2"), encoding="utf-8")
    response = client.get("/annotate?annotator=round1")
    assert response.status_code == 409 and "7-2" in response.get_data(as_text=True)


def finish_round1(client, monkeypatch) -> None:
    monkeypatch.setattr(routes, "now_utc", lambda: T0)
    for qid, choice in [("7-1", "Hard"), ("7-2", "Easy"), ("7-3", "Skip")]:
        label(client, "round1", qid, choice)


def test_round2_is_shut_while_round1_is_unfinished(setup) -> None:
    client, _ = setup
    label(client, "round1", "7-1", "Hard")
    assert "1 of 3 questions labelled" in client.get("/annotate?annotator=round2").get_data(as_text=True)


def test_round2_is_shut_for_48_hours(setup, monkeypatch) -> None:
    client, _ = setup
    finish_round1(client, monkeypatch)
    monkeypatch.setattr(routes, "now_utc", lambda: T0 + timedelta(hours=47))
    assert "Round 2 opens at" in client.get("/annotate?annotator=round2").get_data(as_text=True)


def test_round2_opens_with_graded_questions_and_closes_round1(setup, monkeypatch) -> None:
    client, tmp_path = setup
    finish_round1(client, monkeypatch)
    monkeypatch.setattr(routes, "now_utc", lambda: T0 + timedelta(hours=49))
    page = client.get("/annotate?annotator=round2").get_data(as_text=True)
    queue2 = read_rows(tmp_path / "labels" / "round2_queue.csv")
    assert {row["question_id"] for row in queue2} == {"7-1", "7-2"}  # the Skip is left out
    assert "Your label in this round" not in page  # round 1's labels are never shown
    assert "round 2 has started" in client.get("/annotate?annotator=round1").get_data(as_text=True)
    assert label(client, "round1", "7-1", "Easy").status_code == 200  # refused with a message
    assert len(read_rows(tmp_path / "labels" / "difficulty_round1.csv")) == 3


def test_round2_queue_is_drawn_once(setup, monkeypatch) -> None:
    client, tmp_path = setup
    finish_round1(client, monkeypatch)
    monkeypatch.setattr(routes, "now_utc", lambda: T0 + timedelta(hours=49))
    client.get("/annotate?annotator=round2")
    first = read_rows(tmp_path / "labels" / "round2_queue.csv")
    client.get("/annotate?annotator=round2")
    assert read_rows(tmp_path / "labels" / "round2_queue.csv") == first


def test_all_done_message(setup) -> None:
    client, _ = setup
    for qid in ["7-1", "7-2", "7-3"]:
        label(client, "round1", qid, "Easy")
    assert "3 of 3 questions labelled" in client.get("/annotate?annotator=round1").get_data(as_text=True)


def test_page_links_to_the_original_paper(setup) -> None:
    client, _ = setup
    page = client.get("/annotate?annotator=round1").get_data(as_text=True)
    assert "/paper/7.pdf" in page and "question 1" in page


def test_original_paper_is_served_from_the_manifest(setup) -> None:
    client, _ = setup
    response = client.get("/paper/7.pdf")
    assert response.status_code == 200 and response.mimetype == "application/pdf"
    assert response.data == b"%PDF-1.4 fake"
    response.close()


def test_unknown_paper_is_not_served(setup) -> None:
    client, _ = setup
    assert client.get("/paper/99.pdf").status_code == 404