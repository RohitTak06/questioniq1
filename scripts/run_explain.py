"""Explain every question's difficulty prediction (Phase 6).

Run from the project root, after run_difficulty.py: python scripts/run_explain.py

Writes:
- data/explanations.jsonl: one line per question with its prediction, top SHAP reasons and
  main topics (IDs and numbers only, no exam text)
- reports/metrics/explain.json and reports/figures/shap_importance.png: which features
  matter most overall, and the Logistic Regression coefficients
- reports/explain_review.md (gitignored) and data/explain_check.csv: 20 questions the owner
  didn't label, for the owner's check that the reasons make sense by the rubric
"""

import json
import random
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from questioniq.annotate import add_question_ids, department, labelling_pool, read_rows, write_rows
from questioniq.config import load_config
from questioniq.explain import (
    class_shap_values,
    explain_rows,
    global_importance,
    lr_coefficients,
    topic_explanation,
)

CHECK_COLUMNS = ["review_no", "question_id", "predicted", "matches_rubric", "notes"]


def topic_names_from(rows: list[dict]) -> dict[int, str]:
    """Return the owner's topic names that are filled in, by topic number."""
    return {int(row["topic"]): row["name"].strip() for row in rows if row.get("name", "").strip()}


def importance_figure(importance: dict[str, float], path: Path, top: int = 12) -> None:
    """Draw a bar chart of the features that move predictions most (mean |SHAP|)."""
    items = list(importance.items())[:top][::-1]
    figure, axis = plt.subplots(figsize=(6.5, 4.5))
    axis.barh([name for name, _ in items], [value for _, value in items], color="#4C78A8")
    axis.set_xlabel("Mean |SHAP value| (average effect on predicted probability)")
    axis.set_title("What drives the difficulty predictions (Random Forest)")
    axis.grid(axis="x", alpha=0.3)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def review_markdown(sample: list[dict], explanations: dict[str, dict], questions: dict[str, dict], sheet: str) -> str:
    """Build the owner's review file: question text, prediction and its reasons."""
    lines = [
        "# Explanation check",
        "",
        "These are questions you did not label. For each, read the question and the model's",
        "reasons, and decide: do the reasons make sense by your rubric? Judge the reasons,",
        "not whether the prediction is right. Write yes or no in the `matches_rubric` column",
        f"of `{sheet}`, with a note for any no.",
        "",
    ]
    for number, question_id in enumerate(sample, start=1):
        explanation = explanations[question_id]
        question = questions[question_id]
        shares = ", ".join(f"{label} {p:.2f}" for label, p in explanation["probabilities"].items())
        lines += [f"## {number}. {question_id} ({question['course']})", "", question["text"], "",
                  f"**Prediction:** {explanation['because']} ({shares})", "", "Strongest reasons:", ""]
        lines += [f"- {reason['text']}: {'towards' if reason['shap'] > 0 else 'away from'} "
                  f"{explanation['predicted']} ({reason['shap']:+.3f})" for reason in explanation["reasons"]]
        topics = "; ".join(f"{topic['name']} {topic['share']:.2f}" for topic in explanation["topics"]["topics"])
        lines += ["", f"Topics: {topics or 'none'}", ""]
    return "\n".join(lines)


def main() -> None:
    """Explain all questions and prepare the owner's check."""
    cfg = load_config()
    paths = cfg["paths"]
    settings = cfg["explain"]
    saved = joblib.load(Path(paths["models"]) / "difficulty_random_forest.joblib")
    forest, columns = saved["model"], saved["features"]
    features = pd.read_csv(paths["features"]).set_index("question_id")
    X = features[columns]
    questions = {row["question_id"]: row for row in add_question_ids(read_rows(Path(paths["questions_clean"])))}

    topic_metrics = json.loads((Path(paths["metrics"]) / "topics.json").read_text(encoding="utf-8"))
    topic_model = topic_metrics["chosen_model"]
    keywords = [row["keywords"].split() for row in read_rows(Path(paths["topic_keywords"]))
                if row["model"] == topic_model]
    names = topic_names_from(read_rows(Path(paths["topic_names"])))
    shares = {row["question_id"]: [float(row[f"topic_{n}"]) for n in range(1, len(keywords) + 1)]
              for row in read_rows(Path(paths["question_topics"]))}
    queue_ids = {row["question_id"] for row in read_rows(Path(paths["round1_queue"]))}
    trained_on = set(cfg["annotation"]["departments"])

    explanations = {item["question_id"]: item for item in explain_rows(forest, X, settings["n_reasons"], names)}
    with open(paths["explanations"], "w", encoding="utf-8") as f:
        for question_id, item in explanations.items():
            question = questions[question_id]
            item["department"] = department(question["course"])
            item["outside_training_subjects"] = item["department"] not in trained_on
            item["in_labelled_set"] = question_id in queue_ids
            item["topics"] = topic_explanation(question["clean_text"].split(),
                                               shares.get(question_id, [0.0] * len(keywords)), keywords, names)
            f.write(json.dumps(item) + "\n")

    importance = global_importance(class_shap_values(forest, X), columns)
    importance_figure(importance, Path(paths["figures"]) / "shap_importance.png")
    logistic = joblib.load(Path(paths["models"]) / "difficulty_logistic_regression.joblib")["model"]
    metrics = {
        "explained_model": "random_forest",
        "n_questions": len(explanations),
        "n_outside_training_subjects": sum(item["outside_training_subjects"] for item in explanations.values()),
        "shap_mean_abs": importance,
        "lr_coefficients": lr_coefficients(logistic, columns),
        "topic_names_filled": len(names),
    }
    metrics_dir = Path(paths["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "explain.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    pool = labelling_pool(list(questions.values()), cfg["annotation"]["min_words"], cfg["annotation"]["max_words"],
                          cfg["annotation"]["departments"])
    unlabelled = sorted(row["question_id"] for row in pool if row["question_id"] not in queue_ids)
    sample = random.Random(cfg["random_state"]).sample(unlabelled, settings["n_review"])
    check_path = Path(paths["explain_check"])
    Path(paths["explain_review"]).write_text(
        review_markdown(sample, explanations, questions, check_path.as_posix()), encoding="utf-8")
    if check_path.exists():
        print(f"{check_path} already exists, so it was not overwritten.")
    else:
        write_rows(check_path, [{"review_no": number, "question_id": question_id,
                                 "predicted": explanations[question_id]["predicted"]}
                                for number, question_id in enumerate(sample, start=1)], CHECK_COLUMNS)
    top = ", ".join(list(importance)[:3])
    print(f"EXPLAIN DONE: {len(explanations)} questions explained. Strongest features overall: {top}.")


if __name__ == "__main__":
    main()
