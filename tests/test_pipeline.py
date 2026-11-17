"""The pipeline's order and safety checks, with the stages replaced by a recorder."""

import subprocess
from pathlib import Path

import pytest

from questioniq.pipeline import STEPS, missing_owner_files, run_pipeline


@pytest.fixture
def cfg(tmp_path) -> dict:
    for name in ("manifest.csv", "round1_queue.csv", "topic_names.csv", "labels/difficulty_round1.csv"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fake", encoding="utf-8")
    return {"paths": {"manifest": str(tmp_path / "manifest.csv"), "labels": str(tmp_path / "labels"),
                      "round1_queue": str(tmp_path / "round1_queue.csv"),
                      "topic_names": str(tmp_path / "topic_names.csv")}}


def test_stages_run_in_order_from_pdf_to_database(cfg) -> None:
    ran: list[Path] = []
    assert run_pipeline(cfg, runner=ran.append) == STEPS
    assert [path.stem for path in ran] == STEPS
    assert STEPS[0] == "run_extraction" and STEPS[-1] == "build_db"


def test_every_stage_script_exists() -> None:
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    assert all((scripts / f"{step}.py").is_file() for step in STEPS)


def test_pipeline_stops_before_starting_without_the_owner_files(cfg) -> None:
    Path(cfg["paths"]["topic_names"]).unlink()
    assert missing_owner_files(cfg) == [cfg["paths"]["topic_names"]]
    ran: list[Path] = []
    with pytest.raises(FileNotFoundError):
        run_pipeline(cfg, runner=ran.append)
    assert ran == []


def test_pipeline_stops_at_the_first_failing_stage(cfg) -> None:
    ran: list[str] = []

    def runner(path: Path) -> None:
        ran.append(path.stem)
        if path.stem == "run_topics":
            raise subprocess.CalledProcessError(1, str(path))

    with pytest.raises(subprocess.CalledProcessError):
        run_pipeline(cfg, runner=runner)
    assert ran == STEPS[: STEPS.index("run_topics") + 1]
