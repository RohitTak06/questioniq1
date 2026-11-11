"""Compare OCR cleaning methods against the owner's typed text (Phase 1).

Typed files live in data/ocr_gold/ and are named <paper_id>_p<page>.txt for one page,
or <paper_id>_all.txt for a whole paper typed in page order.

Run from the project root, after typing: python scripts/ocr_eval.py
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

GOLD_NAME = re.compile(r"^(\d+)_(?:p(\d+)|all)\.txt$")


def parse_gold_name(name: str) -> tuple[str, int | None] | None:
    """Return (paper_id, page number) for a typed file, with None as the page for a whole paper."""
    match = GOLD_NAME.match(name)
    if match is None:
        return None
    return match.group(1), int(match.group(2)) if match.group(2) else None


def page_cer(reference: str, hypothesis: str) -> dict:
    """Return the error rate of one typed file, with the reference length for pooling."""
    reference = normalize_for_cer(reference)
    hypothesis = normalize_for_cer(hypothesis)
    return {"cer": character_error_rate(reference, hypothesis), "n_chars": len(reference)}


def pooled_cer(pages: list[dict]) -> float:
    """Return the overall error rate, weighting each typed file by its length."""
    errors = sum(page["cer"] * page["n_chars"] for page in pages)
    return errors / sum(page["n_chars"] for page in pages)


def ocr_text(doc: pymupdf.Document, page_indexes: list[int], method: str, cfg: dict) -> str:
    """OCR some pages of a document with one method and join them in page order."""
    extraction = cfg["extraction"]
    texts = []
    for index in page_indexes:
        image = render_page(doc, index, method, extraction["dpi"])
        texts.append(words_to_text(ocr_words(image, cfg), image.shape[1], extraction["right_zone"]))
    return "\n".join(texts)


def main() -> None:
    """Score every method on every typed file and save the results."""
    cfg = load_config()
    manifest = read_manifest(Path(cfg["paths"]["manifest"]))
    gold_dir = Path(cfg["paths"]["ocr_gold"])
    results: dict[str, dict] = {}
    blank = []
    covered: dict[str, int] = {}
    for gold_path in sorted(gold_dir.glob("*.txt")):
        parsed = parse_gold_name(gold_path.name)
        if parsed is None:
            continue
        reference = gold_path.read_text(encoding="utf-8")
        if not reference.strip():
            blank.append(gold_path.name)
            continue
        paper_id, page_no = parsed
        with pymupdf.open(manifest[paper_id]["path"]) as doc:
            indexes = [page_no - 1] if page_no else list(range(doc.page_count))
            covered[gold_path.stem] = len(indexes)
            for method in METHODS:
                score = page_cer(reference, ocr_text(doc, indexes, method, cfg))
                results.setdefault(method, {"files": {}})["files"][gold_path.stem] = score
        print(f"scored {gold_path.name} ({len(indexes)} pages)", flush=True)
    if not results:
        raise SystemExit(f"No typed files yet in {gold_dir}. Blank files: {blank}")

    for method, result in results.items():
        result["pooled_cer"] = pooled_cer(list(result["files"].values()))
    report = {
        "target": 0.10,
        "method_in_use": cfg["extraction"]["method"],
        "pages_per_file": covered,
        "pages_total": sum(covered.values()),
        "files_not_typed_yet": blank,
        "methods": results,
    }
    metrics_dir = Path(cfg["paths"]["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "ocr.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    for method, result in sorted(results.items(), key=lambda item: item[1]["pooled_cer"]):
        files = ", ".join(f"{name} {f['cer']:.1%}" for name, f in result["files"].items())
        print(f"{method:10s} pooled CER {result['pooled_cer']:.1%}   ({files})")
    if blank:
        print(f"Not typed yet: {blank}")


if __name__ == "__main__":
    main()
