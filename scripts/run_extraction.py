"""Run extraction on every paper in the manifest, once each (Phase 1).

Run from the project root: python scripts/run_extraction.py
"""

import time
from pathlib import Path

from questioniq.config import load_config
from questioniq.extract import extract_cached
from questioniq.scrape import read_manifest


def main() -> None:
    """Extract all papers except those excluded from analysis, printing progress."""
    cfg = load_config()
    manifest = read_manifest(Path(cfg["paths"]["manifest"]))
    excluded = {str(paper_id) for paper_id in cfg["collection"]["exclude_from_analysis"]}
    rows = [row for paper_id, row in manifest.items() if paper_id not in excluded]
    start = time.time()
    for number, row in enumerate(rows, start=1):
        pages = extract_cached(Path(row["path"]), row["paper_id"], cfg)
        tables = sum(page.is_table for page in pages)
        print(
            f"[{number}/{len(rows)}] paper {row['paper_id']}: "
            f"{len(pages)} pages, {tables} table pages",
            flush=True,
        )
    print(f"EXTRACTION DONE: {len(rows)} papers in {time.time() - start:.0f} s", flush=True)


if __name__ == "__main__":
    main()
