"""Year-wise trends of topics and difficulty (Phase 7).

Run from the project root, after run_explain.py: python scripts/run_trends.py

Writes to reports/trends/ (counts and words only, no exam text):
- topic_share_by_year.csv: each topic's share of questions per year and exam type
- difficulty_mix_by_year.csv: predicted Easy/Medium/Hard mix per year, CS and AS only
- owner_labels_by_year.csv: the owner's own labels per year, as a check on the predictions
- recurring_concepts.csv: technical words and word pairs found in 3 or more years
and the figures reports/figures/topic_share_by_year.png and difficulty_mix_by_year.png.
"""

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from questioniq.annotate import add_question_ids, department, read_rows
from questioniq.config import load_config
from questioniq.difficulty import load_training_labels
from questioniq.features import technical_vocabulary
from questioniq.topics import ngram_tokens
from questioniq.trends import GRADES, difficulty_mix_by_year, recurring_concepts, topic_share_by_year

MIN_YEARS = 3


def concept_vocabulary(clean_docs: list[str], min_df: int) -> set[str]:
    """Return the words and word pairs that count as concepts.

    Technical words (high IDF, from Phase 5) plus word pairs found in at least min_df
    questions, so one-off OCR errors are left out.
    """
    pairs = Counter(pair for doc in clean_docs for pair in set(ngram_tokens(doc)) if "_" in pair)
    return technical_vocabulary(clean_docs, min_df) | {pair for pair, n in pairs.items() if n >= min_df}


def share_figure(table: pd.DataFrame, names: dict[int, str], path: Path) -> None:
    """Draw each year's topic mix as stacked bars, with the number of questions on top."""
    pivot = table.pivot_table(index="year", columns="topic", values="share", fill_value=0)
    totals = table.groupby("year")["year_total"].first()
    figure, axis = plt.subplots(figsize=(9, 5))
    bottom = pd.Series(0.0, index=pivot.index)
    colours = plt.get_cmap("tab20").colors
    for index, topic in enumerate(pivot.columns):
        axis.bar(pivot.index.astype(str), pivot[topic], bottom=bottom, color=colours[index % 20],
                 label=names.get(int(topic), f"Topic {topic}"))
        bottom += pivot[topic]
    for position, year in enumerate(pivot.index):
        axis.text(position, 1.01, f"n={totals[year]}", ha="center", fontsize=9)
    axis.set_ylim(0, 1.08)
    axis.set_ylabel("Share of the year's questions")
    axis.set_title("Topic share by year (all subjects)")
    axis.legend(fontsize=7, bbox_to_anchor=(1.01, 1), loc="upper left")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def mix_figure(table: pd.DataFrame, path: Path) -> None:
    """Draw each year's predicted Easy/Medium/Hard mix as stacked bars, with n on top."""
    figure, axis = plt.subplots(figsize=(6.5, 4))
    years = table["year"].astype(str)
    bottom = pd.Series(0.0, index=table.index)
    for grade, colour in zip(GRADES, ["#59A14F", "#F28E2B", "#E15759"]):
        axis.bar(years, table[grade], bottom=bottom, color=colour, label=grade)
        bottom += table[grade]
    for position, n in enumerate(table["n_questions"]):
        axis.text(position, 1.01, f"n={n}", ha="center", fontsize=9)
    axis.set_ylim(0, 1.1)
    axis.set_ylabel("Share of the year's questions")
    axis.set_title("Predicted difficulty by year (CS and AS)")
    axis.legend()
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> None:
    """Build the trend tables and figures."""
    cfg = load_config()
    paths = cfg["paths"]
    questions = pd.DataFrame(add_question_ids(read_rows(Path(paths["questions_clean"]))))
    questions["year"] = pd.to_numeric(questions["year"], errors="coerce").astype("Int64")
    questions["department"] = questions["course"].map(department)
    dominant = {row["question_id"]: int(row["dominant_topic"]) for row in read_rows(Path(paths["question_topics"]))}
    questions["dominant_topic"] = questions["question_id"].map(dominant).fillna(0).astype(int)
    with open(paths["explanations"], encoding="utf-8") as f:
        predicted = {item["question_id"]: item["predicted"] for item in map(json.loads, f)}
    questions["predicted"] = questions["question_id"].map(predicted)
    labels, _ = load_training_labels(paths)
    questions["owner_label"] = questions["question_id"].map(labels)
    names = {int(row["topic"]): row["name"].strip() for row in read_rows(Path(paths["topic_names"]))
             if row.get("name", "").strip()}

    out = Path("reports/trends")
    out.mkdir(parents=True, exist_ok=True)
    shares = topic_share_by_year(questions)
    shares.insert(3, "topic_name", shares["topic"].map(lambda t: names.get(int(t), f"Topic {t}")))
    shares.to_csv(out / "topic_share_by_year.csv", index=False)
    trained = questions[questions["department"].isin(cfg["annotation"]["departments"])]
    mix = difficulty_mix_by_year(trained, "predicted")
    mix.to_csv(out / "difficulty_mix_by_year.csv", index=False)
    difficulty_mix_by_year(questions, "owner_label").to_csv(out / "owner_labels_by_year.csv", index=False)
    vocabulary = concept_vocabulary(questions["clean_text"].tolist(), cfg["topics"]["min_df"])
    questions["concepts"] = questions["clean_text"].map(lambda doc: sorted(set(ngram_tokens(doc)) & vocabulary))
    concepts = recurring_concepts(questions, MIN_YEARS)
    concepts.to_csv(out / "recurring_concepts.csv", index=False)

    share_figure(topic_share_by_year(questions.assign(exam_type="All")), names,
                 Path(paths["figures"]) / "topic_share_by_year.png")
    mix_figure(mix, Path(paths["figures"]) / "difficulty_mix_by_year.png")
    print(f"TRENDS DONE: {questions['year'].nunique()} years, {len(concepts)} concepts in {MIN_YEARS}+ years.")


if __name__ == "__main__":
    main()
