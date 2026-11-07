"""Split every cached paper into questions and report the checks (Phase 1).

Run from the project root, after run_extraction.py: python scripts/run_segmentation.py

Writes data/questions.csv and reports/segmentation_review/ (both gitignored, since
they hold exam text) and reports/segmentation_summary.md (counts and flags only).
"""

import csv
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from questioniq.config import load_config
from questioniq.extract import PageText, load_pages, paper_confidence, paper_text
from questioniq.scrape import read_manifest
from questioniq.segment import Question, check_paper, segment

QUESTION_COLUMNS = [
    "paper_id",
    "course",
    "year",
    "exam_type",
    "qno",
    "sub_part",
    "alternative",
    "marks",
    "co",
    "text",
]


def review_markdown(
    row: dict, questions: list[Question], check: dict, pages: list[PageText]
) -> str:
    """Build one paper's review file: the split questions, then the exact OCR text."""
    lines = [
        f"# Paper {row['paper_id']}: {row['course']} {row['year']} {row['exam_type']}",
        "",
        f"PDF: `{row['path']}`",
        "",
        f"- Questions found: {check['n_questions']}",
        f"- Marks found: {check['marks_total']} (header says {check['max_marks']})",
        f"- Flags: {', '.join(check['flags']) or 'none'}",
        "",
        "## Questions as split",
        "",
    ]
    for number, question in enumerate(questions, start=1):
        label = question.qno + (f" ({question.sub_part})" if question.sub_part else "")
        option = f", OR option {question.alternative}" if question.alternative else ""
        lines.append(
            f"{number}. **Q{label}**{option} [marks {question.marks}, {question.co}]: {question.text}"
        )
    lines += ["", "## Exact OCR text", ""]
    for page in pages:
        kind = "statistical table, skipped" if page.is_table else f"confidence {page.mean_conf}"
        lines += [f"### Page {page.page_no} ({kind})", "", "```", page.text, "```", ""]
    return "\n".join(lines)


def summary_markdown(results: list[tuple[dict, dict]]) -> str:
    """Build the report of counts and flags for all papers. It holds no exam text."""
    total_questions = sum(check["n_questions"] for _, check in results)
    clean = sum(not check["flags"] for _, check in results)
    flag_counts = Counter(flag for _, check in results for flag in check["flags"])
    lines = [
        "# Segmentation summary",
        "",
        f"- Papers: {len(results)}",
        f"- Questions found: {total_questions}",
        f"- Papers with no flags: {clean}",
        "",
        "These checks only point at papers to look at. Passing them does not prove a",
        "paper was split correctly; the hand-checked score in",
        "`reports/metrics/segmentation.json` measures that.",
        "",
        "## Flags",
        "",
        "| Flag | Papers |",
        "| --- | --- |",
    ]
    lines += [f"| {flag} | {count} |" for flag, count in flag_counts.most_common()]
    lines += [
        "",
        "## Per paper",
        "",
        "| Paper | Course | Year | Type | Questions | Marks found | Max marks | Confidence | Flags |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row, check in results:
        flags = ", ".join(check["flags"]) or "-"
        lines.append(
            f"| {row['paper_id']} | {row['course']} | {row['year']} | {row['exam_type']} "
            f"| {check['n_questions']} | {check['marks_total']:g} | {check['max_marks']} "
            f"| {check['mean_conf']} | {flags} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    """Segment all cached papers and write the outputs."""
    cfg = load_config()
    paths = cfg["paths"]
    excluded = {str(paper_id) for paper_id in cfg["collection"]["exclude_from_analysis"]}
    manifest = read_manifest(Path(paths["manifest"]))
    review_dir = Path(paths["seg_review"])
    review_dir.mkdir(parents=True, exist_ok=True)
    results = []
    rows_out = []
    not_cached = []
    for paper_id, row in manifest.items():
        if paper_id in excluded:
            continue
        pages = load_pages(paper_id, cfg)
        if pages is None:
            not_cached.append(paper_id)
            continue
        text = paper_text(pages)
        questions = segment(text)
        check = check_paper(
            questions, text, paper_confidence(pages), cfg["extraction"]["low_confidence"]
        )
        results.append((row, check))
        review = review_markdown(row, questions, check, pages)
        (review_dir / f"{paper_id}.md").write_text(review, encoding="utf-8")
        rows_out += [
            {
                "paper_id": paper_id,
                "course": row["course"],
                "year": row["year"],
                "exam_type": row["exam_type"],
                **asdict(question),
            }
            for question in questions
        ]
    with open(paths["questions"], "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=QUESTION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows_out)
    Path(paths["seg_summary"]).write_text(summary_markdown(results), encoding="utf-8")
    flagged = sum(bool(check["flags"]) for _, check in results)
    print(
        f"SEGMENTATION DONE: {len(results)} papers, {len(rows_out)} questions, "
        f"{flagged} papers flagged, {len(not_cached)} papers without OCR yet.",
        flush=True,
    )


if __name__ == "__main__":
    main()
