"""Pick the pages and papers for the owner's hand work, using a fixed seed (Phase 1).

Run once from the project root: python scripts/select_gold.py
It refuses to run again, because re-drawing could end up favouring easy papers.
Blank files are created for the owner to fill in. Nothing is pre-filled with OCR
text or labels.
"""

import csv
import random
from pathlib import Path

from questioniq.config import load_config
from questioniq.extract import PageText, load_pages, paper_text
from questioniq.scrape import read_manifest
from questioniq.segment import paper_style, segment, split_cells

MIN_WORDS_FOR_GOLD_PAGE = 50
CHECK_COLUMNS = ["paper_id", "course", "pipeline_questions", "owner_total", "owner_correct", "notes"]
TYPING_RULES = """\
## How to type a reference page

- Open the PDF at the page shown, and type into the blank `.txt` file named above.
- Type from the PDF. Do not start from OCR output, or the error rate will come out too low.
- Type line by line, left to right across the whole page, including headers, the marks
  and CO column, and "Page 1 of 4". Don't type the watermark.
- Type symbols as best you can (λ, ≤, x^2). Missing symbols will count as OCR errors,
  which is correct: they are.
- Case and punctuation count. Spacing and table lines don't.
"""
CHECK_RULES = """\
## How to check a paper

For each paper, open its PDF next to `reports/segmentation_review/<paper_id>.md`, and fill in
`data/seg_gold/segmentation_check.csv`:

- `owner_total`: how many questions the paper really has, counting by the rule below.
- `owner_correct`: how many of those appear in the review file as one correct row: the right
  start and end, not merged with another question and not cut in two.
- `notes`: anything odd. OCR typos inside a question don't make it wrong here; the OCR score
  measures those.

The counting rule: one row per question, except that sub-parts count separately only when
each has its own marks, and each OR option counts separately. MCQ options are not separate.
"""


def choose_gold_pages(candidates: list[dict], rng: random.Random) -> list[dict]:
    """Pick one page each from the low, middle and high thirds of OCR confidence."""
    ranked = sorted(candidates, key=lambda page: (page["mean_conf"], page["paper_id"], page["page_no"]))
    third = len(ranked) // 3
    bands = [ranked[:third], ranked[third : 2 * third], ranked[2 * third :]]
    chosen: list[dict] = []
    for band in bands:
        fresh = [page for page in band if page["paper_id"] not in {c["paper_id"] for c in chosen}]
        chosen.append(rng.choice(fresh))
    return chosen


def allocate(sizes: dict[str, int], n: int) -> dict[str, int]:
    """Share n picks across groups in proportion to size, with at least one for each group."""
    total = sum(sizes.values())
    shares = {name: max(1, int(n * size / total)) for name, size in sizes.items() if size}
    by_size = sorted(shares, key=lambda name: -sizes[name])
    index = 0
    while sum(shares.values()) < n and by_size:
        name = by_size[index % len(by_size)]
        if shares[name] < sizes[name]:
            shares[name] += 1
        index += 1
    while sum(shares.values()) > n:
        name = max(shares, key=lambda key: shares[key])
        shares[name] -= 1
    return shares


def choose_papers(
    by_style: dict[str, list[str]], n: int, rng: random.Random
) -> list[str]:
    """Pick n papers across numbering styles, so the sample isn't only the common layout."""
    shares = allocate({style: len(ids) for style, ids in by_style.items()}, n)
    picked: list[str] = []
    for style, count in sorted(shares.items()):
        picked += rng.sample(sorted(by_style[style], key=int), count)
    return sorted(picked, key=int)


def page_candidates(paper_id: str, pages: list[PageText]) -> list[dict]:
    """Return a paper's pages that are fit to be typed: real text, not tables or blanks."""
    return [
        {"paper_id": paper_id, "page_no": page.page_no, "mean_conf": page.mean_conf}
        for page in pages
        if not page.is_table
        and page.mean_conf is not None
        and len(page.text.split()) >= MIN_WORDS_FOR_GOLD_PAGE
    ]


def main() -> None:
    """Draw the selections, write the instructions and create blank files to fill in."""
    cfg = load_config()
    paths = cfg["paths"]
    selection_path = Path(paths["gold_selection"])
    if selection_path.exists():
        raise SystemExit(f"{selection_path} already exists, so nothing was re-drawn.")
    rng = random.Random(cfg["random_state"])
    excluded = {str(paper_id) for paper_id in cfg["collection"]["exclude_from_analysis"]}
    manifest = read_manifest(Path(paths["manifest"]))

    candidates: list[dict] = []
    by_style: dict[str, list[str]] = {}
    counts: dict[str, int] = {}
    for paper_id in manifest:
        if paper_id in excluded:
            continue
        pages = load_pages(paper_id, cfg)
        if pages is None:
            raise SystemExit(f"Paper {paper_id} has no OCR yet. Run run_extraction.py first.")
        candidates += page_candidates(paper_id, pages)
        text = paper_text(pages)
        style = paper_style([split_cells(line)[0] for line in text.splitlines()])
        by_style.setdefault(style, []).append(paper_id)
        counts[paper_id] = len(segment(text))

    gold_pages = choose_gold_pages(candidates, rng)
    check_papers = choose_papers(by_style, cfg["gold"]["n_check_papers"], rng)
    remaining = {
        style: [paper_id for paper_id in ids if paper_id not in check_papers]
        for style, ids in by_style.items()
    }
    line_papers = choose_papers(remaining, cfg["gold"]["n_line_papers"], rng)

    gold_dir = Path(paths["ocr_gold"])
    gold_dir.mkdir(parents=True, exist_ok=True)
    for page in gold_pages:
        (gold_dir / f"{page['paper_id']}_p{page['page_no']}.txt").touch()

    check_path = Path(paths["seg_check"])
    check_path.parent.mkdir(parents=True, exist_ok=True)
    with open(check_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CHECK_COLUMNS)
        writer.writeheader()
        for paper_id in check_papers:
            writer.writerow(
                {
                    "paper_id": paper_id,
                    "course": manifest[paper_id]["course"],
                    "pipeline_questions": counts[paper_id],
                }
            )

    lines = [
        "# Hand-work selection",
        "",
        f"Drawn once with `random_state={cfg['random_state']}`; papers are not swapped afterwards.",
        "",
        "## 3 pages to type (one each from low, middle and high OCR confidence)",
        "",
        "| Type into | PDF | Page | OCR confidence |",
        "| --- | --- | --- | --- |",
    ]
    for page in gold_pages:
        row = manifest[page["paper_id"]]
        lines.append(
            f"| `data/ocr_gold/{page['paper_id']}_p{page['page_no']}.txt` | `{row['path']}` "
            f"| {page['page_no']} | {page['mean_conf']} |"
        )
    lines += ["", TYPING_RULES, f"## {len(check_papers)} papers to check", ""]
    lines += ["| Paper | Course | PDF |", "| --- | --- | --- |"]
    lines += [
        f"| {paper_id} | {manifest[paper_id]['course']} | `{manifest[paper_id]['path']}` |"
        for paper_id in check_papers
    ]
    lines += ["", CHECK_RULES, "## Numbering styles across all papers", ""]
    lines += [f"- {style}: {len(ids)} papers" for style, ids in sorted(by_style.items())]
    lines += ["", "## Reserved papers for the fallback model (only if we keep it)", ""]
    lines += [", ".join(line_papers), ""]
    selection_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"SELECTION DONE: see {selection_path}", flush=True)


if __name__ == "__main__":
    main()
