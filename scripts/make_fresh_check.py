"""Create the blank sheet for the second segmentation check, on fresh papers (Phase 1).

Run once from the project root, after run_segmentation.py: python scripts/make_fresh_check.py

The first check (data/seg_gold/segmentation_check.csv) was used to find and fix rule
gaps, so scoring those papers again would overstate the result. This sheet lists the
reserved papers from reports/gold_selection.md, which were never looked at while fixing.
It refuses to overwrite a sheet that already exists. Nothing is pre-filled except the
pipeline's own question count.
"""

import csv
from pathlib import Path

from questioniq.config import load_config
from questioniq.extract import load_pages, paper_text
from questioniq.scrape import read_manifest
from questioniq.segment import segment

try:  # run as python scripts/make_fresh_check.py
    from select_gold import CHECK_COLUMNS, CHECK_RULES
except ModuleNotFoundError:  # imported by the tests as scripts.make_fresh_check
    from scripts.select_gold import CHECK_COLUMNS, CHECK_RULES


def blank_rows(paper_ids: list[str], manifest: dict, counts: dict[str, int]) -> list[dict]:
    """Return one blank check row per paper, with only the pipeline's count filled in."""
    return [
        {"paper_id": paper_id, "course": manifest[paper_id]["course"], "pipeline_questions": counts[paper_id]}
        for paper_id in paper_ids
    ]


def instructions(paper_ids: list[str], manifest: dict, sheet: str) -> str:
    """Return the instructions for the owner, with the paper list."""
    lines = [
        "# Second segmentation check (fresh papers)",
        "",
        "The segmentation rules were fixed after the first check and are now frozen.",
        "These papers were reserved when the first selection was drawn and were not",
        "looked at while fixing, so this score is the honest one.",
        "",
        "| Paper | Course | PDF | Review file |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {paper_id} | {manifest[paper_id]['course']} | `{manifest[paper_id]['path']}` "
        f"| `reports/segmentation_review/{paper_id}.md` |"
        for paper_id in paper_ids
    ]
    rules = CHECK_RULES.replace("data/seg_gold/segmentation_check.csv", sheet)
    return "\n".join(lines) + "\n\n" + rules


def main() -> None:
    """Write the blank sheet and the instructions."""
    cfg = load_config()
    paths = cfg["paths"]
    sheet = Path(paths["seg_check_fresh"])
    if sheet.exists():
        raise SystemExit(f"{sheet} already exists, so nothing was overwritten.")
    paper_ids = [str(paper_id) for paper_id in cfg["gold"]["fresh_check_papers"]]
    manifest = read_manifest(Path(paths["manifest"]))
    counts = {}
    for paper_id in paper_ids:
        pages = load_pages(paper_id, cfg)
        if pages is None:
            raise SystemExit(f"Paper {paper_id} has no OCR yet. Run run_extraction.py first.")
        counts[paper_id] = len(segment(paper_text(pages)))
    sheet.parent.mkdir(parents=True, exist_ok=True)
    with open(sheet, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CHECK_COLUMNS)
        writer.writeheader()
        writer.writerows(blank_rows(paper_ids, manifest, counts))
    guide = Path("reports/fresh_check.md")
    guide.write_text(instructions(paper_ids, manifest, sheet.as_posix()), encoding="utf-8")
    print(f"FRESH CHECK READY: fill in {sheet}, instructions in {guide}", flush=True)


if __name__ == "__main__":
    main()
