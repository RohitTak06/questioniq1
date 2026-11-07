"""config.yaml loads and holds the values the project rules depend on."""

from pathlib import Path

import pytest

from questioniq.config import load_config

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


@pytest.fixture
def cfg() -> dict:
    return load_config(CONFIG_PATH)


def test_random_state_is_42(cfg: dict) -> None:
    assert cfg["random_state"] == 42


def test_k_range_is_4_to_15(cfg: dict) -> None:
    assert (cfg["topics"]["k_min"], cfg["topics"]["k_max"]) == (4, 15)


def test_portal_delay_is_at_least_one_second(cfg: dict) -> None:
    assert cfg["portal"]["min_delay_seconds"] >= 1.0


def test_tesseract_cmd_exists(cfg: dict) -> None:
    assert Path(cfg["tesseract_cmd"]).is_file()
