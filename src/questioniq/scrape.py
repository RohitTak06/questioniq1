"""Download previous-year papers from the JKLU Paper Portal (Phase 0b)."""

from pathlib import Path

import pandas as pd
from playwright.sync_api import APIRequestContext


def list_papers(session: APIRequestContext) -> list[dict]:
    """Return every paper on the portal with its metadata."""
    raise NotImplementedError


def choose_subjects(catalogue: pd.DataFrame, min_subjects: int) -> list[str]:
    """Pick course codes: papers in 2 or more years first, then the most papers."""
    raise NotImplementedError


def download_paper(session: APIRequestContext, paper: dict, dest: Path) -> Path:
    """Download one paper to dest and return its path."""
    raise NotImplementedError


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    raise NotImplementedError


def write_manifest(rows: list[dict], path: Path) -> None:
    """Write one row per downloaded paper to the manifest CSV."""
    raise NotImplementedError
