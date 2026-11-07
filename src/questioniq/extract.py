"""Get text out of a PDF: pdfplumber first, Tesseract OCR for scanned pages (Phase 1)."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class PageText:
    """The text of one PDF page and how it was obtained."""

    page_no: int
    text: str
    has_text_layer: bool
    ocr_used: bool


def extract_text(pdf_path: Path, cfg: dict) -> list[PageText]:
    """Return the text of each page, using OCR when a page has no usable text layer."""
    raise NotImplementedError


def reduce_watermark(image: np.ndarray) -> np.ndarray:
    """Clean a rendered page before OCR by suppressing the light diagonal watermark."""
    raise NotImplementedError


def is_table_page(text: str) -> bool:
    """Return True if a page is a statistical table (mostly digits in a grid)."""
    raise NotImplementedError


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Return Levenshtein distance divided by the length of the reference text."""
    raise NotImplementedError
