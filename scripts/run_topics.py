"""Sweep k for LDA and NMF, pick the best by C_v, and save the topics (Phase 3).

Run from the project root, after run_preprocess.py: python scripts/run_topics.py

Writes:
- reports/figures/coherence_vs_k.png and reports/metrics/topics.json
- reports/topic_keywords.csv: top words of every topic, for both models at their best k
- data/question_topics.csv: each question's main topic and topic shares (no exam text)
- reports/topic_by_department.csv: how many questions of each department fall in each topic
- models/topics_lda.joblib and models/topics_nmf.joblib
- data/topic_names.csv: the chosen model's topics with a blank name column for the owner.
  It is never overwritten once it exists, since the names are the owner's work.
"""

import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from questioniq.annotate import add_question_ids, department, read_rows, write_rows
from questioniq.config import load_config
from questioniq.topics import (
    MODEL_KINDS,
    best_k,
    choose_model,
    dominant_topics,
    fit_model,
    subject_alignment,
    sweep_k,
    top_keywords,
    topic_by_group,
    topic_distribution,
)

NAME_COLUMNS = ["model", "k", "topic", "keywords", "name"]


def coherence_figure(sweep: pd.DataFrame, best: dict, path: Path) -> None:
    """Plot C_v against k for both models, marking each model's best k."""
    figure, axis = plt.subplots(figsize=(7, 4))
    for kind, rows in sweep.groupby("model"):
        axis.plot(rows["k"], rows["c_v"], marker="o", label=str(kind).upper())
        axis.scatter([best[kind]["k"]], [best[kind]["c_v"]], s=120, facecolors="none", edgecolors="black")
    axis.set_xlabel("Number of topics (k)")
    axis.set_ylabel("C_v coherence")
    axis.set_title("Topic coherence by k (circled: best k)")
    axis.set_xticks(sorted(sweep["k"].unique()))
    axis.legend()
    axis.grid(alpha=0.3)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def keyword_rows(kind: str, k: int, topics: list[list[str]]) -> list[dict]:
    """Return one row per topic with its top words, topics numbered from 1."""
    return [{"model": kind, "k": k, "topic": number, "keywords": " ".join(words)}
            for number, words in enumerate(topics, start=1)]


def question_topic_rows(
    questions: list[dict], kind: str, distribution: np.ndarray, dominant: list[int]
) -> list[dict]:
    """Return each question's ID, main topic and topic shares. No exam text."""
    rows = []
    for question, shares, main in zip(questions, distribution, dominant):
        row = {key: question[key] for key in ("question_id", "paper_id", "course", "year", "exam_type")}
        row.update({"model": kind, "dominant_topic": main})
        row.update({f"topic_{number}": round(float(share), 4) for number, share in enumerate(shares, start=1)})
        rows.append(row)
    return rows


def main() -> None:
    """Run the sweep, pick the model and write the outputs."""
    cfg = load_config()
    paths = cfg["paths"]
    settings = cfg["topics"]
    random_state = cfg["random_state"]
    questions = [row for row in add_question_ids(read_rows(Path(paths["questions_clean"])))
                 if int(row["n_tokens"]) > 0]
    docs = [row["clean_text"] for row in questions]

    sweep = sweep_k(docs, settings, random_state)
    best = best_k(sweep)
    chosen = choose_model(best)
    coherence_figure(sweep, best, Path(paths["figures"]) / "coherence_vs_k.png")

    keywords, fitted = [], {}
    models_dir = Path(paths["models"])
    models_dir.mkdir(parents=True, exist_ok=True)
    for kind in MODEL_KINDS:
        k = best[kind]["k"]
        model, vectorizer = fit_model(kind, docs, k, settings, random_state)
        topics = top_keywords(model, list(vectorizer.get_feature_names_out()), settings["top_n"])
        keywords += keyword_rows(kind, k, topics)
        fitted[kind] = (model, vectorizer, topics)
        joblib.dump({"kind": kind, "k": k, "model": model, "vectorizer": vectorizer},
                    models_dir / f"topics_{kind}.joblib")
    write_rows(Path(paths["topic_keywords"]), keywords, ["model", "k", "topic", "keywords"])

    model, vectorizer, topics = fitted[chosen]
    distribution = topic_distribution(model, vectorizer, docs)
    dominant = dominant_topics(distribution)
    rows = question_topic_rows(questions, chosen, distribution, dominant)
    write_rows(Path(paths["question_topics"]), rows, list(rows[0]))
    departments = [department(row["course"]) for row in questions]
    topic_by_group(dominant, departments).to_csv(paths["topic_by_department"])
    alignment = subject_alignment(dominant, departments)

    k = best[chosen]["k"]
    metrics = {
        "n_questions": len(docs),
        "settings": settings,
        "sweep": sweep.round(4).to_dict(orient="records"),
        "best": best,
        "chosen_model": chosen,
        "chosen_k": k,
        "subject_alignment": alignment,
    }
    metrics_dir = Path(paths["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "topics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    names_path = Path(paths["topic_names"])
    if names_path.exists():
        existing = read_rows(names_path)
        if {(row["model"], row["k"]) for row in existing} != {(chosen, str(k))}:
            print(f"WARNING: {names_path} names topics of another model or k; check it before using it.")
        else:
            print(f"{names_path} already exists, so it was not overwritten.")
    else:
        write_rows(names_path, [{**row, "name": ""} for row in keyword_rows(chosen, k, topics)], NAME_COLUMNS)

    print(f"TOPICS DONE: LDA best k={best['lda']['k']} (C_v {best['lda']['c_v']:.3f}), "
          f"NMF best k={best['nmf']['k']} (C_v {best['nmf']['c_v']:.3f}); chosen {chosen.upper()} k={k}. "
          f"Topic-department NMI {alignment['nmi']}.")


if __name__ == "__main__":
    main()
