"""Run every stage over the whole manifest and store the results (Phase 7).

Each stage is one script in scripts/, run in order as its own process, exactly as if
you ran it by hand. The pipeline stops at the first stage that fails. Stages are safe to
repeat: OCR comes from the cache, models use random_state=42, and no stage overwrites the
owner's labels, rubric, topic names or check sheets.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

STEPS = [
    "run_extraction",  # PDF -> text (OCR from the cache; new papers are OCR'd)
    "run_segmentation",  # text -> questions
    "run_preprocess",  # questions -> cleaned words
    "run_topics",  # LDA vs NMF, best k by C_v
    "run_difficulty",  # features, RF vs LR vs baseline, save the model
    "run_explain",  # SHAP reasons and topics for every question
    "run_trends",  # year-wise tables and figures
    "make_figures",  # the report's dataset and evaluation figures
    "build_db",  # everything into data/questioniq.db
]


def missing_owner_files(cfg: dict) -> list[str]:
    """Return the owner's files the pipeline needs but can't find (it never creates them)."""
    paths = cfg["paths"]
    needed = [Path(paths["manifest"]), Path(paths["labels"]) / "difficulty_round1.csv",
              Path(paths["round1_queue"]), Path(paths["topic_names"])]
    return [str(path) for path in needed if not path.exists()]


def run_script(path: Path) -> None:
    """Run one stage script with the project's Python, stopping the pipeline if it fails."""
    subprocess.run([sys.executable, str(path)], check=True)


def run_pipeline(
    cfg: dict, runner: Callable[[Path], None] = run_script, scripts_dir: Path = Path("scripts")
) -> list[str]:
    """Rebuild the database from data/raw/: extract, segment, preprocess, model, explain, store.

    Returns the stages that ran. Stops with an error before starting if the owner's
    files are missing, and at the first stage that fails.
    """
    missing = missing_owner_files(cfg)
    if missing:
        raise FileNotFoundError(f"The pipeline needs these files first: {', '.join(missing)}")
    for step in STEPS:
        print(f"== {step}", flush=True)
        runner(scripts_dir / f"{step}.py")
    return list(STEPS)
