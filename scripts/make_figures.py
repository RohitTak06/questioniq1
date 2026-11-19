"""Make the report's dataset and evaluation figures (Phase 9).

Run from the project root, after the other stages: python scripts/make_figures.py
It is the pipeline's second-to-last stage, so run_pipeline.py refreshes every figure.

The model figures are made by the stage that produces them:
- run_topics.py: coherence_vs_k.png
- run_difficulty.py: confusion_<model>.png
- run_explain.py: shap_importance.png
- run_trends.py: topic_share_by_year.png, difficulty_mix_by_year.png
This script adds, from the saved data and metrics:
- dataset_by_year.png, dataset_by_department.png
- ocr_by_method.png, segmentation_before_after.png
- label_distribution.png, and kappa_matrix.png once round 2 is scored
"""

import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from questioniq.annotate import GRADES, add_question_ids, department, read_rows
from questioniq.config import load_config
from questioniq.difficulty import load_training_labels
from questioniq.scrape import read_manifest

BLUE, ORANGE, GREY = "#4C78A8", "#F58518", "#9AA5B1"
GRADE_COLOURS = {"Easy": "#59A14F", "Medium": "#F28E2B", "Hard": "#E15759"}


def _save(figure: plt.Figure, path: Path) -> None:
    """Save a figure at 150 dpi, creating its folder, and close it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _label_bars(axis: plt.Axes, bars, fmt: str = "{:g}") -> None:
    """Write each bar's value just above it."""
    for bar in bars:
        axis.annotate(fmt.format(bar.get_height()), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                      ha="center", va="bottom", fontsize=8, xytext=(0, 2), textcoords="offset points")


def dataset_by_year(papers_per_year: dict, questions_per_year: dict, path: Path) -> None:
    """Draw papers and questions per year side by side."""
    years = sorted(set(papers_per_year) | set(questions_per_year))
    figure, (left, right) = plt.subplots(1, 2, figsize=(9, 3.6))
    _label_bars(left, left.bar([str(y) for y in years], [papers_per_year.get(y, 0) for y in years], color=BLUE))
    left.set_title("Papers per year")
    _label_bars(right, right.bar([str(y) for y in years], [questions_per_year.get(y, 0) for y in years], color=ORANGE))
    right.set_title("Questions per year")
    _save(figure, path)


def dataset_by_department(questions_per_department: dict, labelled: set[str], path: Path) -> None:
    """Draw questions per department, marking the departments the difficulty model learned from."""
    items = sorted(questions_per_department.items(), key=lambda item: item[1])
    figure, axis = plt.subplots(figsize=(6.5, 4.8))
    colours = [ORANGE if name in labelled else BLUE for name, _ in items]
    bars = axis.barh([name for name, _ in items], [n for _, n in items], color=colours)
    for bar in bars:
        axis.annotate(f"{bar.get_width():g}", (bar.get_width(), bar.get_y() + bar.get_height() / 2),
                      va="center", fontsize=8, xytext=(3, 0), textcoords="offset points")
    axis.set_xlabel("Questions")
    axis.set_title(f"Questions per department (orange: labelled for difficulty, {' + '.join(sorted(labelled))})")
    _save(figure, path)


def ocr_by_method(methods: dict, chosen: str, target: float, path: Path) -> None:
    """Draw the pooled character error rate of each OCR method against the target."""
    names = sorted(methods, key=lambda name: methods[name])
    figure, axis = plt.subplots(figsize=(5.5, 3.6))
    bars = axis.bar(names, [methods[name] * 100 for name in names],
                    color=[ORANGE if name == chosen else GREY for name in names])
    _label_bars(axis, bars, "{:.1f}%")
    axis.axhline(target * 100, color="black", linestyle="--", linewidth=1)
    axis.text(len(names) - 0.5, target * 100, f" target ≤ {target:.0%}", va="bottom", ha="right", fontsize=8)
    axis.set_ylabel("Character error rate (%)")
    axis.set_title(f"OCR error by method (chosen: {chosen})")
    _save(figure, path)


def segmentation_before_after(before: float, after: float, target: float, path: Path) -> None:
    """Draw the segmentation score before the rule fixes and on fresh papers after them."""
    figure, axis = plt.subplots(figsize=(5, 3.6))
    bars = axis.bar(["Before fixes\n(10 studied papers)", "After fixes\n(10 fresh papers)"],
                    [before * 100, after * 100], color=[GREY, ORANGE])
    _label_bars(axis, bars, "{:.1f}%")
    axis.axhline(target * 100, color="black", linestyle="--", linewidth=1)
    axis.text(1.4, target * 100, f"target {target:.0%}", va="bottom", ha="right", fontsize=8)
    axis.set_ylim(0, 100)
    axis.set_ylabel("Questions split correctly (%)")
    axis.set_title("Question segmentation")
    _save(figure, path)


def label_distribution(counts: dict, title: str, path: Path) -> None:
    """Draw how many questions the owner gave each difficulty grade."""
    figure, axis = plt.subplots(figsize=(4.8, 3.6))
    bars = axis.bar(GRADES, [counts.get(grade, 0) for grade in GRADES], color=[GRADE_COLOURS[g] for g in GRADES])
    _label_bars(axis, bars)
    axis.set_ylabel("Questions")
    axis.set_title(title)
    _save(figure, path)


def matrix_figure(matrix: list[list[int]], labels: list[str], xlabel: str, ylabel: str, title: str, path: Path) -> None:
    """Draw a square count matrix, such as round 1 against round 2."""
    figure, axis = plt.subplots(figsize=(4.2, 3.6))
    axis.imshow(matrix, cmap="Blues")
    biggest = max(max(row) for row in matrix) or 1
    for row, values in enumerate(matrix):
        for column, value in enumerate(values):
            axis.text(column, row, str(value), ha="center", va="center",
                      color="white" if value > biggest / 2 else "black")
    axis.set_xticks(range(len(labels)), labels)
    axis.set_yticks(range(len(labels)), labels)
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.set_title(title)
    _save(figure, path)


def main() -> None:
    """Make every dataset and evaluation figure that its data exists for."""
    cfg = load_config()
    paths = cfg["paths"]
    out = Path(paths["figures"])
    metrics_dir = Path(paths["metrics"])
    excluded = {str(paper_id) for paper_id in cfg["collection"]["exclude_from_analysis"]}
    papers = [row for paper_id, row in read_manifest(Path(paths["manifest"])).items() if paper_id not in excluded]
    questions = add_question_ids(read_rows(Path(paths["questions_clean"])))
    made = []

    dataset_by_year(Counter(int(p["year"]) for p in papers if p["year"].isdigit()),
                    Counter(int(q["year"]) for q in questions if q["year"].isdigit()), out / "dataset_by_year.png")
    dataset_by_department(Counter(department(q["course"]) for q in questions),
                          set(cfg["annotation"]["departments"]), out / "dataset_by_department.png")
    made += ["dataset_by_year", "dataset_by_department"]

    def metric(name: str) -> dict | None:
        path = metrics_dir / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    ocr = metric("ocr")
    if ocr:
        pooled = {name: values["pooled_cer"] for name, values in ocr["methods"].items()}
        ocr_by_method(pooled, ocr["method_in_use"], ocr["target"], out / "ocr_by_method.png")
        made.append("ocr_by_method")
    segmentation = metric("segmentation")
    if segmentation and segmentation["score"] is not None:
        segmentation_before_after(segmentation["studied_papers_before_fixes"]["score"], segmentation["score"],
                                  segmentation["target"], out / "segmentation_before_after.png")
        made.append("segmentation_before_after")
    labels, source = load_training_labels(paths)
    if labels:
        label_distribution(Counter(labels.values()), f"Owner's difficulty labels ({len(labels)}, {source})",
                           out / "label_distribution.png")
        made.append("label_distribution")
    kappa = metric("kappa")
    if kappa:
        agreement = kappa["round1_vs_round2"]
        matrix_figure(agreement["confusion_matrix"], agreement["labels"], "Round 2", "Round 1",
                      f"Round 1 vs round 2 (Kappa {agreement['kappa']:.2f})", out / "kappa_matrix.png")
        made.append("kappa_matrix")
    print(f"FIGURES DONE: {', '.join(made)}")


if __name__ == "__main__":
    main()
