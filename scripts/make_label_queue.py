"""Draw the round-1 labelling queue once (Phase 4).

Run from the project root, after run_preprocess.py: python scripts/make_label_queue.py

Writes data/labels/round1_queue.csv: question IDs, paper, course and a text fingerprint,
no exam text. It refuses to run again, because re-drawing could favour easy questions.
"""

import random
from collections import Counter
from pathlib import Path

from questioniq.annotate import (
    QUEUE_COLUMNS,
    add_question_ids,
    department,
    draw_round1,
    labelling_pool,
    read_rows,
    write_rows,
)
from questioniq.config import load_config


def main() -> None:
    """Draw the queue and print how it is spread across departments."""
    cfg = load_config()
    paths = cfg["paths"]
    settings = cfg["annotation"]
    queue_path = Path(paths["round1_queue"])
    if queue_path.exists():
        raise SystemExit(f"{queue_path} already exists, so nothing was re-drawn.")
    rows = add_question_ids(read_rows(Path(paths["questions_clean"])))
    if not rows:
        raise SystemExit("No cleaned questions found. Run scripts/run_preprocess.py first.")
    pool = labelling_pool(rows, settings["min_words"], settings["max_words"], settings.get("departments"))
    queue = draw_round1(pool, settings["round1_n"], random.Random(cfg["random_state"]))
    write_rows(queue_path, queue, QUEUE_COLUMNS)
    spread = Counter(department(row["course"]) for row in queue)
    print(f"QUEUE DRAWN: {len(queue)} of {len(pool)} usable questions ({len(rows)} in total).")
    print("By department: " + ", ".join(f"{name} {n}" for name, n in spread.most_common()))


if __name__ == "__main__":
    main()
