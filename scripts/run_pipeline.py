"""Rebuild everything from data/raw/ with one command (Phase 7).

Run from the project root: python scripts/run_pipeline.py
"""

import time

from questioniq.config import load_config
from questioniq.pipeline import run_pipeline


def main() -> None:
    """Run all stages in order and report the time taken."""
    start = time.time()
    steps = run_pipeline(load_config())
    print(f"PIPELINE DONE: {len(steps)} stages in {time.time() - start:.0f} s", flush=True)


if __name__ == "__main__":
    main()
