"""The hand-work selection and scoring logic. All data here is fake."""

import random

import pytest

from questioniq.extract import PageText
from scripts.ocr_eval import page_cer, parse_gold_name, pooled_cer
from scripts.run_segmentation import review_markdown, summary_markdown
from scripts.make_fresh_check import blank_rows, instructions
from scripts.seg_eval import combined_report, score_rows
from scripts.select_gold import allocate, choose_gold_pages, choose_papers, page_candidates
from questioniq.segment import Question


def test_gold_pages_come_from_three_confidence_bands_and_three_papers() -> None:
    candidates = [
        {"paper_id": str(n), "page_no": 1, "mean_conf": float(n)} for n in range(1, 31)
    ]
    chosen = choose_gold_pages(candidates, random.Random(42))
    confidences = [page["mean_conf"] for page in chosen]
    assert confidences[0] <= 10 < confidences[1] <= 20 < confidences[2]
    assert len({page["paper_id"] for page in chosen}) == 3


def test_gold_page_choice_is_repeatable() -> None:
    candidates = [{"paper_id": str(n), "page_no": 1, "mean_conf": float(n)} for n in range(30)]
    first = choose_gold_pages(candidates, random.Random(42))
    assert first == choose_gold_pages(candidates, random.Random(42))


def test_page_candidates_leaves_out_tables_and_nearly_blank_pages() -> None:
    long_text = " ".join(["fake"] * 60)
    pages = [
        PageText(1, long_text, False, True, False, 80.0),
        PageText(2, long_text, False, True, True, 80.0),
        PageText(3, "fake", False, True, False, 80.0),
    ]
    assert [page["page_no"] for page in page_candidates("7", pages)] == [1]


@pytest.mark.parametrize(
    "sizes, n, expected",
    [
        ({"q": 100, "number": 40, "table": 9}, 10, {"q": 7, "number": 2, "table": 1}),
        ({"q": 148, "none": 1}, 10, {"q": 9, "none": 1}),
        ({"q": 5}, 5, {"q": 5}),
    ],
)
def test_allocate_is_proportional_and_keeps_every_group(sizes: dict, n: int, expected: dict) -> None:
    assert allocate(sizes, n) == expected


def test_choose_papers_returns_n_distinct_papers_and_is_repeatable() -> None:
    by_style = {"q": [str(n) for n in range(100)], "none": ["200"]}
    picked = choose_papers(by_style, 10, random.Random(42))
    assert len(set(picked)) == 10
    assert "200" in picked
    assert picked == choose_papers(by_style, 10, random.Random(42))


@pytest.mark.parametrize(
    "name, expected",
    [("101_p1.txt", ("101", 1)), ("89_all.txt", ("89", None)), (".gitkeep", None), ("101_p1.md", None)],
)
def test_parse_gold_name_accepts_single_pages_and_whole_papers(name: str, expected: tuple | None) -> None:
    assert parse_gold_name(name) == expected


def test_page_cer_ignores_spacing_and_table_lines_but_not_case() -> None:
    assert page_cer("Find  X", "| Find X |")["cer"] == 0
    assert page_cer("abcd", "abcD")["cer"] == 0.25


def test_pooled_cer_weights_pages_by_length() -> None:
    pages = [{"cer": 0.5, "n_chars": 100}, {"cer": 0.0, "n_chars": 300}]
    assert pooled_cer(pages) == 0.125


def check_row(paper_id: str, total: str, correct: str) -> dict:
    return {"paper_id": paper_id, "pipeline_questions": "6", "owner_total": total, "owner_correct": correct}


def test_score_counts_questions_not_papers() -> None:
    report = score_rows([check_row("1", "10", "9"), check_row("2", "30", "27")])
    assert report["score"] == 0.9
    assert (report["n_correct"], report["n_total"]) == (36, 40)


def test_score_lists_papers_not_checked_and_does_not_count_them() -> None:
    report = score_rows([check_row("1", "10", "9"), check_row("2", "", "")])
    assert report["n_total"] == 10
    assert report["not_checked_yet"] == ["2"]


def test_score_with_nothing_checked_yet() -> None:
    assert score_rows([check_row("1", "", "")])["score"] is None


ROW = {"paper_id": "7", "course": "XX1", "year": "2024", "exam_type": "Endterm", "path": "fake.pdf"}
CHECK = {
    "n_questions": 1,
    "marks_total": 5.0,
    "n_missing_marks": 0,
    "max_marks": 5.0,
    "number_jumps": [],
    "mean_conf": 80.0,
    "flags": ["low_confidence"],
}


def test_summary_counts_flags_per_paper() -> None:
    text = summary_markdown([(ROW, CHECK)])
    assert "| low_confidence | 1 |" in text
    assert "| 7 | XX1 | 2024 | Endterm | 1 | 5 | 5.0 | 80.0 | low_confidence |" in text


def test_review_shows_split_questions_and_exact_text() -> None:
    questions = [Question("1", "a", "Fake question", 5.0, "CO1", 2)]
    pages = [PageText(1, "Exact fake OCR", False, True, False, 80.0)]
    text = review_markdown(ROW, questions, CHECK, pages)
    assert "**Q1 (a)**, OR option 2 [marks 5.0, CO1]: Fake question" in text
    assert "Exact fake OCR" in text


def test_final_score_comes_only_from_the_fresh_papers() -> None:
    report = combined_report([check_row("1", "10", "5")], [check_row("2", "10", "9")])
    assert report["score"] == 0.9
    assert report["studied_papers_before_fixes"]["score"] == 0.5


def test_no_final_score_before_the_fresh_sheet_exists() -> None:
    report = combined_report([check_row("1", "10", "5")], None)
    assert report["score"] is None
    assert report["fresh_papers_after_fixes"] is None


def test_fresh_sheet_rows_are_blank_except_the_pipeline_count() -> None:
    manifest = {"7": {"course": "XX1", "path": "fake.pdf"}}
    assert blank_rows(["7"], manifest, {"7": 4}) == [
        {"paper_id": "7", "course": "XX1", "pipeline_questions": 4}
    ]


def test_fresh_instructions_point_at_the_fresh_sheet() -> None:
    manifest = {"7": {"course": "XX1", "path": "fake.pdf"}}
    text = instructions(["7"], manifest, "data/seg_gold/fresh.csv")
    assert "data/seg_gold/fresh.csv" in text
    assert "segmentation_check.csv" not in text
    assert "reports/segmentation_review/7.md" in text
