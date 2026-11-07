"""Load project settings from config.yaml."""

from pathlib import Path

import yaml


def load_config(path: Path = Path("config.yaml")) -> dict:
    """Read the YAML config file and return it as a dictionary."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
