"""Measure how consistently the owner labels: round 1 vs round 2 (Phase 4).

Run from the project root, after round 2: python scripts/kappa.py

Writes:
- reports/metrics/kappa.json: Cohen's Kappa, agreement and confusion matrix (no text)
- reports/kappa_disagreements.md: the questions where the rounds differ, with their text
  (gitignored)
- data/labels/settled_labels.csv: one row per disagreement with a blank final_label for
  the owner to fill in. It is never overwritten once it exists.
"""

import json
from pathlib import Path

from questioniq.annotate import (
    add_question_ids,
    agreement_report,
    latest_labels,
    read_rows,
    write_rows,
)
from questioniq.config import load_config

TARGET = 0.6
SETTLE_COLUMNS = ["question_id", "round1", "round2", "final_label", "notes"]


def disagreements_markdown(report: dict, questions: dict[str, dict], sheet: str) -> str:
    """Build the owner's list of disagreements, with each question's text."""
    lines = [
        "# Labels that differ between round 1 and round 2",
        "",
        f"Decide the final label for each and write it in the `final_label` column of `{sheet}`.",
        "",
    ]
    for item in report["disagreements"]:
        question = questions.get(item["question_id"], {})
        lines += [
            f"## {item['question_id']} ({question.get('course', '?')}): "
            f"round 1 {item['first']}, round 2 {item['second']}",
            "",
            question.get("text", "(question not found)"),
            "",
        ]
    return "\n".join(lines)


def settle_rows(report: dict) -> list[dict]:
    """Return the blank settle sheet: one row per disagreement."""
    return [
        {"question_id": item["question_id"], "round1": item["first"], "round2": item["second"]}
        for item in report["disagreements"]
    ]


def main() -> None:
    """Compare the rounds and write the outputs."""
    cfg = load_config()
    paths = cfg["paths"]
    labels_dir = Path(paths["labels"])
    round1 = latest_labels(read_rows(labels_dir / "difficulty_round1.csv"))
    round2 = latest_labels(read_rows(labels_dir / "difficulty_round2.csv"))
    if not round2:
        raise SystemExit("No round-2 labels yet.")
    report = agreement_report(round1, round2)
    helper = latest_labels(read_rows(labels_dir / "difficulty_helper.csv"))
    summary = {
        "target": TARGET,
        "round1_vs_round2": {key: value for key, value in report.items() if key != "disagreements"},
        "n_disagreements": len(report["disagreements"]),
    }
    if helper:
        helper_report = agreement_report(round1, helper)
        summary["round1_vs_helper"] = {k: v for k, v in helper_report.items() if k != "disagreements"}
    metrics_dir = Path(paths["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "kappa.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    questions = {row["question_id"]: row for row in add_question_ids(read_rows(Path(paths["questions_clean"])))}
    sheet = Path(paths["settle_sheet"])
    Path(paths["kappa_disagreements"]).write_text(
        disagreements_markdown(report, questions, sheet.as_posix()), encoding="utf-8"
    )
    if sheet.exists():
        print(f"{sheet} already exists, so it was not overwritten.")
    else:
        write_rows(sheet, settle_rows(report), SETTLE_COLUMNS)

    kappa = report["kappa"]
    shown = f"{kappa:.3f}" if kappa is not None else "not defined"
    print(f"Round 1 vs round 2 on {report['n_compared']} questions: Kappa {shown} (target {TARGET}), "
          f"{len(report['disagreements'])} disagreements.")


if __name__ == "__main__":
    main()
