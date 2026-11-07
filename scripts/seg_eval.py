"""Score segmentation from the owner's hand checks (Phase 1).

Run from the project root, after filling in data/seg_gold/segmentation_check.csv:
python scripts/seg_eval.py
Writes reports/metrics/segmentation.json and prints the score.
"""

import csv
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


def main() -> None:
    """Read the owner's checks and save the score."""
    cfg = load_config()
    with open(cfg["paths"]["seg_check"], encoding="utf-8", newline="") as f:
        report = score_rows(list(csv.DictReader(f)))
    metrics_dir = Path(cfg["paths"]["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "segmentation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for paper_id, paper in report["papers"].items():
        print(
            f"paper {paper_id}: {paper['owner_correct']}/{paper['owner_total']} correct, "
            f"pipeline found {paper['pipeline_questions']}"
        )
    if report["score"] is not None:
        print(f"Score: {report['n_correct']}/{report['n_total']} = {report['score']:.1%} (target 90%)")
    if report["not_checked_yet"]:
        print(f"Not checked yet: {report['not_checked_yet']}")


if __name__ == "__main__":
    main()
