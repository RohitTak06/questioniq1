"""Report figures, drawn from made-up numbers into a temporary folder."""

from pathlib import Path

from scripts.make_figures import (
    dataset_by_department,
    dataset_by_year,
    label_distribution,
    matrix_figure,
    ocr_by_method,
    segmentation_before_after,
)


def is_png(path: Path) -> bool:
    return path.is_file() and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_every_figure_is_written_as_a_png(tmp_path) -> None:
    dataset_by_year({2023: 5, 2024: 3}, {2023: 40, 2024: 20, 2025: 2}, tmp_path / "year.png")
    dataset_by_department({"CS": 30, "ME": 10}, {"CS"}, tmp_path / "dept.png")
    ocr_by_method({"layers": 0.08, "otsu": 0.15}, "layers", 0.10, tmp_path / "ocr.png")
    segmentation_before_after(0.489, 0.80, 0.90, tmp_path / "seg.png")
    label_distribution({"Easy": 3, "Hard": 1}, "Fake labels", tmp_path / "labels.png")
    matrix_figure([[3, 1, 0], [0, 2, 1], [0, 0, 4]], ["Easy", "Medium", "Hard"], "Round 2", "Round 1",
                  "Fake agreement", tmp_path / "nested" / "kappa.png")
    names = ["year", "dept", "ocr", "seg", "labels", "nested/kappa"]
    assert all(is_png(tmp_path / f"{name}.png") for name in names)
