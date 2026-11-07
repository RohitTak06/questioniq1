"""Compare OCR cleaning methods against the owner's typed pages (Phase 1).

Run from the project root, after typing the pages: python scripts/ocr_eval.py
Writes reports/metrics/ocr.json and prints the character error rate of each method.
"""

import json
import re
from pathlib import Path

import pymupdf

from questioniq.config import load_config
from questioniq.extract import (
    METHODS,
    character_error_rate,
    normalize_for_cer,
    ocr_words,
    render_page,
    words_to_text,
)
from questioniq.scrape import read_manifest

GOLD_NAME = re.compile(r"^(\d+)_p(\d+)\.txt$")


def page_cer(reference: str, hypothesis: str) -> dict:
    """Return the error rate of one page, with the reference length for pooling."""
    reference = normalize_for_cer(reference)
    hypothesis = normalize_for_cer(hypothesis)
    return {"cer": character_error_rate(reference, hypothesis), "n_chars": len(reference)}


def pooled_cer(pages: list[dict]) -> float:
    """Return the overall error rate, weighting each page by its length."""
    errors = sum(page["cer"] * page["n_chars"] for page in pages)
    return errors / sum(page["n_chars"] for page in pages)


def main() -> None:
    """Score every method on every typed page and save the results."""
    cfg = load_config()
    extraction = cfg["extraction"]
    manifest = read_manifest(Path(cfg["paths"]["manifest"]))
    gold_dir = Path(cfg["paths"]["ocr_gold"])
    results: dict[str, dict] = {}
    blank = []
    for gold_path in sorted(gold_dir.glob("*.txt")):
        match = GOLD_NAME.match(gold_path.name)
        if match is None:
            continue
        reference = gold_path.read_text(encoding="utf-8")
        if not reference.strip():
            blank.append(gold_path.name)
            continue
        paper_id, page_no = match.group(1), int(match.group(2))
        with pymupdf.open(manifest[paper_id]["path"]) as doc:
            for method in METHODS:
                image = render_page(doc, page_no - 1, method, extraction["dpi"])
                text = words_to_text(ocr_words(image, cfg), image.shape[1], extraction["right_zone"])
                score = page_cer(reference, text)
                results.setdefault(method, {"pages": {}})["pages"][gold_path.stem] = score
    if not results:
        raise SystemExit(f"No typed pages yet in {gold_dir}. Blank files: {blank}")

    for method, result in results.items():
        result["pooled_cer"] = pooled_cer(list(result["pages"].values()))
    report = {
        "target": 0.10,
        "method_in_use": extraction["method"],
        "pages_not_typed_yet": blank,
        "methods": results,
    }
    metrics_dir = Path(cfg["paths"]["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "ocr.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    for method, result in sorted(results.items(), key=lambda item: item[1]["pooled_cer"]):
        pages = ", ".join(f"{name} {p['cer']:.1%}" for name, p in result["pages"].items())
        print(f"{method:10s} pooled CER {result['pooled_cer']:.1%}   ({pages})")
    if blank:
        print(f"Not typed yet: {blank}")


if __name__ == "__main__":
    main()
