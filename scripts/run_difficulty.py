"""Build features, compare the difficulty models and save the best one (Phase 5).

Run from the project root, after run_topics.py: python scripts/run_difficulty.py
Run it again after round 2 is settled: settled labels then replace round 1 where they differ.

Writes:
- data/features.csv: every question's features (no exam text)
- reports/metrics/difficulty.json and reports/difficulty_results.md: the comparison
- reports/figures/confusion_<model>.png
- models/difficulty.joblib: the better model, tuned on all labelled questions
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from questioniq.annotate import add_question_ids, latest_labels, read_rows
from questioniq.config import load_config
from questioniq.difficulty import choose_best, compare_models, fit_final, save_best, training_labels
from questioniq.features import feature_names, feature_table, load_bloom_verbs, technical_vocabulary

NICE_NAMES = {"random_forest": "Random Forest", "logistic_regression": "Logistic Regression",
              "majority_baseline": "Majority baseline"}


def results_markdown(results: dict, chosen: str, n_labelled: int, label_counts: dict, source: str) -> str:
    """Build the results table: macro-F1, accuracy and per-class F1 for every model."""
    lines = [
        "# Difficulty model results",
        "",
        f"- Labelled questions: {n_labelled} ({', '.join(f'{k} {v}' for k, v in label_counts.items())}), "
        "CS and AS only",
        f"- Labels: {source}",
        "- Scores: nested stratified 5-fold CV (grid search inside each training part), random_state=42",
        f"- Chosen model: **{NICE_NAMES[chosen]}**",
        "",
        "| Model | Macro-F1 (mean ± sd) | Accuracy | Easy F1 | Medium F1 | Hard F1 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, result in results.items():
        per_class = result["per_class"]
        lines.append(
            f"| {NICE_NAMES[name]} | {result['macro_f1_mean']:.3f} ± {result['macro_f1_std']:.3f} "
            f"| {result['accuracy']:.3f} | {per_class['Easy']['f1-score']:.3f} "
            f"| {per_class['Medium']['f1-score']:.3f} | {per_class['Hard']['f1-score']:.3f} |"
        )
    lines += ["", "## Per-class precision and recall", ""]
    for name, result in results.items():
        lines += [f"**{NICE_NAMES[name]}**", "", "| Class | Precision | Recall | F1 | Support |",
                  "| --- | --- | --- | --- | --- |"]
        lines += [f"| {label} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1-score']:.3f} | {int(s['support'])} |"
                  for label, s in result["per_class"].items()]
        lines.append("")
    return "\n".join(lines)


def confusion_figure(result: dict, title: str, path: Path) -> None:
    """Draw a confusion matrix: rows are the owner's labels, columns the model's predictions."""
    matrix = result["confusion_matrix"]
    labels = result["labels"]
    figure, axis = plt.subplots(figsize=(4.2, 3.6))
    axis.imshow(matrix, cmap="Blues")
    for row, values in enumerate(matrix):
        for column, value in enumerate(values):
            colour = "white" if value > max(map(max, matrix)) / 2 else "black"
            axis.text(column, row, str(value), ha="center", va="center", color=colour)
    axis.set_xticks(range(len(labels)), labels)
    axis.set_yticks(range(len(labels)), labels)
    axis.set_xlabel("Predicted")
    axis.set_ylabel("Owner's label")
    axis.set_title(title)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> None:
    """Build features, compare models and save the outputs."""
    cfg = load_config()
    paths = cfg["paths"]
    questions = add_question_ids(read_rows(Path(paths["questions_clean"])))
    topic_rows = read_rows(Path(paths["question_topics"]))
    dominant = {row["question_id"]: int(row["dominant_topic"]) for row in topic_rows}
    k = json.loads((Path(paths["metrics"]) / "topics.json").read_text(encoding="utf-8"))["chosen_k"]
    verbs, phrases = load_bloom_verbs(Path(paths["bloom_verbs"]))
    technical = technical_vocabulary([row["clean_text"] for row in questions if row["clean_text"]],
                                     cfg["topics"]["min_df"])
    features = feature_table(questions, dominant, k, verbs, phrases, technical)
    features.to_csv(paths["features"], index=False)

    labels_dir = Path(paths["labels"])
    round1 = latest_labels(read_rows(labels_dir / "difficulty_round1.csv"))
    queue_ids = [row["question_id"] for row in read_rows(Path(paths["round1_queue"]))]
    settled_rows = [row for row in read_rows(Path(paths["settle_sheet"])) if row.get("final_label", "").strip()]
    settled = {row["question_id"]: row["final_label"].strip() for row in settled_rows}
    labels = training_labels(round1, queue_ids, settled)
    source = "round 1" + (f", with {len(settled)} settled after round 2" if settled else " (round 2 not settled yet)")

    columns = feature_names(k)
    X = features.set_index("question_id").loc[list(labels), columns]
    y = pd.Series(labels).loc[X.index]
    results = compare_models(X, y, cfg)
    chosen = choose_best(results)
    model = fit_final(chosen, X, y, cfg)
    save_best(model, Path(paths["models"]) / "difficulty.joblib",
              {"name": chosen, "features": columns, "labels": cfg["difficulty"]["labels"],
               "n_trained": len(y), "departments": cfg["annotation"]["departments"], "label_source": source})

    label_counts = {label: int((y == label).sum()) for label in cfg["difficulty"]["labels"]}
    metrics = {"n_labelled": len(y), "label_counts": label_counts, "label_source": source,
               "features": columns, "chosen_model": chosen, "results": results}
    metrics_dir = Path(paths["metrics"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "difficulty.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    Path(paths["difficulty_results"]).write_text(
        results_markdown(results, chosen, len(y), label_counts, source), encoding="utf-8")
    for name, result in results.items():
        confusion_figure(result, NICE_NAMES[name], Path(paths["figures"]) / f"confusion_{name}.png")

    summary = ", ".join(f"{NICE_NAMES[name]} {result['macro_f1_mean']:.3f}" for name, result in results.items())
    print(f"DIFFICULTY DONE on {len(y)} labelled questions. Macro-F1: {summary}. Chosen: {NICE_NAMES[chosen]}.")


if __name__ == "__main__":
    main()
