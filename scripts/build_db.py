"""Rebuild the SQLite database from the pipeline's output files (Phase 7).

Run from the project root, after run_trends.py: python scripts/build_db.py
Writes data/questioniq.db (gitignored, since it holds exam text).
"""

import json
from pathlib import Path

from questioniq.annotate import add_question_ids, department, read_rows
from questioniq.config import load_config
from questioniq.db import build_database
from questioniq.difficulty import load_training_labels
from questioniq.scrape import read_manifest


def gather_sources(cfg: dict) -> dict:
    """Read every file the database is built from."""
    paths = cfg["paths"]
    excluded = {str(paper_id) for paper_id in cfg["collection"]["exclude_from_analysis"]}
    papers = [row for paper_id, row in read_manifest(Path(paths["manifest"])).items() if paper_id not in excluded]
    topics = read_rows(Path(paths["topic_names"]))
    shares = {row["question_id"]: [float(row[f"topic_{n}"]) for n in range(1, len(topics) + 1)]
              for row in read_rows(Path(paths["question_topics"]))}
    with open(paths["explanations"], encoding="utf-8") as f:
        explanations = {item["question_id"]: item for item in map(json.loads, f)}
    labels, _ = load_training_labels(paths)
    return {
        "papers": papers,
        "departments": {row["paper_id"]: department(row["course"]) for row in papers},
        "questions": add_question_ids(read_rows(Path(paths["questions_clean"]))),
        "topics": topics,
        "shares": shares,
        "explanations": explanations,
        "labels": labels,
    }


def main() -> None:
    """Rebuild the database and print how many rows each table got."""
    cfg = load_config()
    counts = build_database(gather_sources(cfg), Path(cfg["paths"]["db"]))
    print("DATABASE BUILT: " + ", ".join(f"{table} {n}" for table, n in counts.items()))


if __name__ == "__main__":
    main()
