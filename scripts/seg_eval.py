"""Score segmentation from the owner's hand checks (Phase 1).

Run from the project root, after filling in data/seg_gold/segmentation_check.csv:
python scripts/seg_eval.py
Writes reports/metrics/segmentation.json and prints the score.
"""

import csv
import io
import json
from pathlib import Path

from questioniq.config import load_config

TARGET = 0.90


def score_rows(rows: list[dict]) -> dict:
    """Return per-paper and overall scores. Papers not checked yet are listed, not counted."""
    checked = [row for row in rows if row["owner_total"].strip() and row["owner_correct"].strip()]
    papers = {
        row["paper_id"]: {
            "owner_total": int(row["owner_total"]),
            "owner_correct": int(row["owner_correct"]),
            "pipeline_questions": int(row["pipeline_questions"]),
        }
        for row in checked
    }
    total = sum(paper["owner_total"] for paper in papers.values())
    correct = sum(paper["owner_correct"] for paper in papers.values())
    return {
        "target": TARGET,
        "score": correct / total if total else None,
        "n_correct": correct,
        "n_total": total,
        "papers": papers,
        "not_checked_yet": [row["paper_id"] for row in rows if row not in checked],
    }


def read_sheet(path: Path) -> list[dict] | None:
    """Return the rows of a check sheet, or None if it doesn't exist yet.

    Excel on Windows saves CSV files in the Windows-1252 character set, not UTF-8, so that
    is tried when the file isn't valid UTF-8.
    """
    if not path.exists():
        return None
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def combined_report(first: list[dict], fresh: list[dict] | None) -> dict:
    """Return both checks. The fresh one is the score that counts.

    The first check's papers were used to fix the rules, so their score is kept only as
    the "before" number, measured with the rules as they were then.
    """
    first_report = score_rows(first)
    fresh_report = score_rows(fresh) if fresh is not None else None
    return {
        "target": TARGET,
        "score": fresh_report["score"] if fresh_report else None,
        "score_source": "fresh_papers_after_fixes",
        "fresh_papers_after_fixes": fresh_report,
        "studied_papers_before_fixes": first_report,
    }


def print_report(name: str, report: dict) -> None:
    """Print one check's per-paper counts and score."""
    print(f"== {name}")
    for paper_id, paper in report["papers"].items():
        print(
            f"paper {paper_id}: {paper['owner_correct']}/{paper['owner_total']} correct, "
            f"pipeline found {paper['pipeline_questions']}"
        )
    if report["score"] is not None:
        print(f"Score: {report['n_correct']}/{report['n_total']} = {report['score']:.1%} (target 90%)")
    if report["not_checked_yet"]:
        print(f"Not checked yet: {report['not_checked_yet']}")


def main() -> None:
    """Read the owner's checks and save the scores."""
    cfg = load_config()
    first = read_sheet(Path(cfg["paths"]["seg_check"]))
    if first is None:
        raise SystemExit("The first check sheet is missing.")
    fresh = read_sheet(Path(cfg["paths"]["seg_check_fresh"]))
    report = combined_report(first, fresh)
    metrics_dir = Path(cfg["paths"]["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "segmentation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_report("Studied papers, rules before the fixes (not the final score)", report["studied_papers_before_fixes"])
    if report["fresh_papers_after_fixes"] is None:
        print("== Fresh papers: sheet not created yet (run scripts/make_fresh_check.py)")
    else:
        print_report("Fresh papers, frozen rules (the score that counts)", report["fresh_papers_after_fixes"])


if __name__ == "__main__":
    main()
