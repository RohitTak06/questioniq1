"""Clean every question's text for topic modelling (Phase 2).

Run from the project root, after run_segmentation.py: python scripts/run_preprocess.py

Writes:
- data/questions_clean.csv: every question with its raw text and a clean_text column
  (gitignored, since it holds exam text)
- reports/preprocess_summary.md: counts and the most common words only
- reports/preprocess_review.md: 20 questions drawn with random_state, raw next to clean
  (gitignored), and a blank data/preprocess_check.csv for the owner's yes/no check
"""

import csv
import random
from collections import Counter
from pathlib import Path
from statistics import median

from questioniq.config import load_config
from questioniq.preprocess import clean_question

CHECK_COLUMNS = ["review_no", "paper_id", "qno", "sub_part", "alternative", "reads_as_topic", "notes"]


def add_clean_text(rows: list[dict], extra_stopwords: set[str], min_length: int) -> list[dict]:
    """Return the rows with clean_text and n_tokens added. The raw text is left as it is."""
    cleaned = []
    for row in rows:
        clean = clean_question(row["text"], extra_stopwords, min_length)
        cleaned.append({**row, "clean_text": clean, "n_tokens": len(clean.split())})
    return cleaned


def document_frequency(rows: list[dict]) -> Counter:
    """Return how many questions each cleaned word appears in."""
    return Counter(word for row in rows for word in set(row["clean_text"].split()))


def summary_markdown(rows: list[dict], min_df: int, top_n: int = 30) -> str:
    """Build the report of counts and common words. It holds no question text."""
    counts = [row["n_tokens"] for row in rows]
    df = document_frequency(rows)
    empty = sum(count == 0 for count in counts)
    lines = [
        "# Preprocessing summary",
        "",
        f"- Questions: {len(rows)}",
        f"- Questions left empty after cleaning: {empty}",
        f"- Tokens per question: median {median(counts) if counts else 0}, "
        f"max {max(counts, default=0)}",
        f"- Vocabulary: {len(df)} words, {sum(n >= min_df for n in df.values())} "
        f"in at least {min_df} questions (the topic models' min_df)",
        "",
        f"## {top_n} most common words (number of questions containing each)",
        "",
        "| Word | Questions |",
        "| --- | --- |",
    ]
    lines += [f"| {word} | {n} |" for word, n in df.most_common(top_n)]
    return "\n".join(lines) + "\n"


def review_sample(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Draw n questions that still have words after cleaning, in a fixed random order."""
    usable = [row for row in rows if row["n_tokens"] > 0]
    return rng.sample(usable, min(n, len(usable)))


def review_markdown(sample: list[dict], sheet: str) -> str:
    """Build the owner's review file: each sampled question raw, then cleaned."""
    lines = [
        "# Preprocessing check",
        "",
        "For each question, read the cleaned words and decide whether they still say what",
        f"the question is about. Write yes or no in the `reads_as_topic` column of `{sheet}`,",
        "and a note for any no (for example, a key word that was removed).",
        "",
    ]
    for number, row in enumerate(sample, start=1):
        label = row["qno"] + (f" ({row['sub_part']})" if row["sub_part"] else "")
        lines += [
            f"## {number}. Paper {row['paper_id']} ({row['course']}), Q{label}",
            "",
            f"**Raw:** {row['text']}",
            "",
            f"**Clean:** {row['clean_text']}",
            "",
        ]
    return "\n".join(lines)


def check_rows(sample: list[dict]) -> list[dict]:
    """Return the blank check sheet rows for the sample."""
    return [
        {
            "review_no": number,
            "paper_id": row["paper_id"],
            "qno": row["qno"],
            "sub_part": row["sub_part"],
            "alternative": row["alternative"],
        }
        for number, row in enumerate(sample, start=1)
    ]


def main() -> None:
    """Clean all questions and write the outputs."""
    cfg = load_config()
    paths = cfg["paths"]
    settings = cfg["preprocess"]
    with open(paths["questions"], encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    rows = add_clean_text(rows, set(settings["exam_stopwords"]), settings["min_token_length"])

    with open(paths["questions_clean"], "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    Path(paths["preprocess_summary"]).write_text(
        summary_markdown(rows, cfg["topics"]["min_df"]), encoding="utf-8"
    )

    sample = review_sample(rows, settings["n_review"], random.Random(cfg["random_state"]))
    check_path = Path(paths["preprocess_check"])
    Path(paths["preprocess_review"]).write_text(
        review_markdown(sample, check_path.as_posix()), encoding="utf-8"
    )
    if check_path.exists():
        print(f"{check_path} already exists, so it was not overwritten.")
    else:
        with open(check_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CHECK_COLUMNS)
            writer.writeheader()
            writer.writerows(check_rows(sample))
    empty = sum(row["n_tokens"] == 0 for row in rows)
    print(f"PREPROCESSING DONE: {len(rows)} questions, {empty} empty after cleaning.", flush=True)


if __name__ == "__main__":
    main()
