"""Score the owner's explanation check (Phase 6).

Run from the project root, after filling in data/explain_check.csv:
python scripts/explain_eval.py
Writes reports/metrics/explain_check.json and prints the result against the target
(at least 15 of 20 explanations make sense by the owner's rubric).
"""

import json
from pathlib import Path

from questioniq.config import load_config

try:  # run as python scripts/explain_eval.py
    from seg_eval import read_sheet
except ModuleNotFoundError:  # imported by the tests as scripts.explain_eval
    from scripts.seg_eval import read_sheet


def score_explanations(rows: list[dict], target: int) -> dict:
    """Count the owner's yes and no answers and compare the yes count with the target."""
    answers = {row["review_no"]: row["matches_rubric"].strip().lower() for row in rows}
    answered = [number for number, answer in answers.items() if answer in ("yes", "no")]
    yes = sum(answers[number] == "yes" for number in answered)
    return {
        "n_checked": len(answered),
        "n_yes": yes,
        "target": target,
        "passes": len(answered) == len(rows) and yes >= target,
        "no": [{"review_no": row["review_no"], "question_id": row["question_id"], "notes": row["notes"].strip()}
               for row in rows if answers[row["review_no"]] == "no"],
        "not_answered": [number for number in answers if number not in answered],
    }


def main() -> None:
    """Read the owner's check and save the score."""
    cfg = load_config()
    rows = read_sheet(Path(cfg["paths"]["explain_check"]))
    if rows is None:
        raise SystemExit("The check sheet is missing. Run scripts/run_explain.py first.")
    report = score_explanations(rows, cfg["explain"]["target_matches"])
    metrics_dir = Path(cfg["paths"]["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "explain_check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    verdict = "passes" if report["passes"] else "does not pass yet"
    print(f"{report['n_yes']} of {report['n_checked']} explanations make sense (target {report['target']}): {verdict}.")


if __name__ == "__main__":
    main()
