"""Score the owner's preprocessing check (Phase 2).

Run from the project root, after filling in data/preprocess_check.csv:
python scripts/preprocess_eval.py
Writes reports/metrics/preprocess.json and prints the result.
"""

import json
from pathlib import Path

from questioniq.config import load_config

try:  # run as python scripts/preprocess_eval.py
    from seg_eval import read_sheet
except ModuleNotFoundError:  # imported by the tests as scripts.preprocess_eval
    from scripts.seg_eval import read_sheet


def score_check(rows: list[dict]) -> dict:
    """Count the owner's yes and no answers; rows not answered yet are listed, not counted."""
    answers = {row["review_no"]: row["reads_as_topic"].strip().lower() for row in rows}
    answered = {number: answer for number, answer in answers.items() if answer in ("yes", "no")}
    yes = sum(answer == "yes" for answer in answered.values())
    return {
        "n_checked": len(answered),
        "n_yes": yes,
        "share_yes": yes / len(answered) if answered else None,
        "no": [
            {"review_no": row["review_no"], "paper_id": row["paper_id"], "notes": row["notes"].strip()}
            for row in rows
            if answers[row["review_no"]] == "no"
        ],
        "not_answered": [number for number in answers if number not in answered],
    }


def main() -> None:
    """Read the owner's check and save the score."""
    cfg = load_config()
    rows = read_sheet(Path(cfg["paths"]["preprocess_check"]))
    if rows is None:
        raise SystemExit("The check sheet is missing. Run scripts/run_preprocess.py first.")
    report = score_check(rows)
    metrics_dir = Path(cfg["paths"]["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "preprocess.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{report['n_yes']} of {report['n_checked']} cleaned questions still read as their topic.")
    for item in report["no"]:
        print(f"  no: #{item['review_no']} (paper {item['paper_id']}): {item['notes']}")


if __name__ == "__main__":
    main()
