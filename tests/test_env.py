"""The pinned libraries import, and Tesseract runs."""

import importlib
from pathlib import Path

import pytesseract
import pytest

from questioniq.config import load_config

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

IMPORT_NAMES = [
    "pdfplumber",
    "pymupdf",
    "pytesseract",
    "cv2",
    "PIL",
    "nltk",
    "sklearn",
    "gensim",
    "shap",
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "sqlalchemy",
    "flask",
    "joblib",
    "yaml",
    "requests",
    "pytest",
    "playwright",
]


@pytest.mark.parametrize("name", IMPORT_NAMES)
def test_library_imports(name: str) -> None:
    importlib.import_module(name)


def test_tesseract_returns_a_version() -> None:
    pytesseract.pytesseract.tesseract_cmd = load_config(CONFIG_PATH)["tesseract_cmd"]
    assert pytesseract.get_tesseract_version().major >= 5
