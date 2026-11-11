"""Get text out of a PDF: pdfplumber first, Tesseract OCR for scanned pages (Phase 1)."""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pdfplumber
import pymupdf
import pytesseract

METHODS = ("otsu", "adaptive", "layers")
RIGHT_CELL = re.compile(
    r"^[\[(]?\d{1,2}(\.\d)?[\])]?[,.]?$"  # 5, 10.0, [5], (5)
    r"|^\(?[CLI][O0][\dlI,]*\)?[,.]?$",  # CO1, CO1,2, (LO3), and OCR variants such as COl
)


@dataclass
class PageText:
    """The text of one PDF page and how it was obtained."""

    page_no: int
    text: str
    has_text_layer: bool
    ocr_used: bool
    is_table: bool = False
    mean_conf: float | None = None
    words: list[dict] = field(default_factory=list)
    render_method: str | None = None


def clean_page(gray: np.ndarray, method: str) -> np.ndarray:
    """Turn a grayscale page into black text on white, reducing the watermark.

    "otsu" picks one global threshold. "adaptive" stretches contrast, then
    thresholds each pixel against its neighbourhood.
    """
    if method == "otsu":
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    if method == "adaptive":
        low, high = np.percentile(gray, (1, 99))
        scaled = (gray.astype(float) - low) * 255 / max(high - low, 1)
        stretched = np.clip(scaled, 0, 255).astype("uint8")
        return cv2.adaptiveThreshold(
            stretched, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15
        )
    raise ValueError(f"Unknown method: {method}")


def foreground_layers(doc: pymupdf.Document, page: pymupdf.Page, dpi: int) -> np.ndarray:
    """Draw only the page's 1-bit scan layers on white, leaving out the watermark images."""
    scale = dpi / 72
    width, height = int(page.rect.width * scale), int(page.rect.height * scale)
    canvas = np.full((height, width), 255, np.uint8)
    for info in page.get_images(full=True):
        xref, image_filter = info[0], info[8]
        if image_filter != "CCITTFaxDecode":
            continue
        pixmap = pymupdf.Pixmap(doc, xref)
        if pixmap.n > 1:
            pixmap = pymupdf.Pixmap(pymupdf.csGRAY, pixmap)
        image = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.h, pixmap.w)
        for rect in page.get_image_rects(xref):
            x0, y0 = int(rect.x0 * scale), int(rect.y0 * scale)
            x1, y1 = int(rect.x1 * scale), int(rect.y1 * scale)
            if x1 <= x0 or y1 <= y0:
                continue
            piece = cv2.resize(image, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
            left, top = max(x0, 0), max(y0, 0)
            right, bottom = min(x1, width), min(y1, height)
            piece = piece[top - y0 : bottom - y0, left - x0 : right - x0]
            canvas[top:bottom, left:right] = np.minimum(canvas[top:bottom, left:right], piece)
    return canvas


def has_scan_layers(page: pymupdf.Page) -> bool:
    """Return True if a page is built from 1-bit scan layers, which the layers method needs."""
    return any(info[8] == "CCITTFaxDecode" for info in page.get_images(full=True))


def page_method(doc: pymupdf.Document, page_index: int, method: str) -> str:
    """Return the method actually used for a page: layers falls back to otsu without scan layers."""
    if method == "layers" and not has_scan_layers(doc[page_index]):
        return "otsu"
    return method


def keep_layers(layers_words: int, otsu_words: int, min_ratio: float, min_words: int) -> bool:
    """Return True if layers kept enough of the text that otsu found on the same page.

    On some scans the text sits in a colour layer that layers leaves out, so most words vanish.
    """
    if otsu_words < min_words:
        return True
    return layers_words >= min_ratio * otsu_words


def render_page(doc: pymupdf.Document, page_index: int, method: str, dpi: int) -> np.ndarray:
    """Render one page to a cleaned image, ready for OCR."""
    page = doc[page_index]
    method = page_method(doc, page_index, method)
    if method == "layers":
        return foreground_layers(doc, page, dpi)
    pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    gray = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.h, pixmap.w)
    return clean_page(gray, method)


def ocr_words(image: np.ndarray, cfg: dict) -> list[dict]:
    """Run Tesseract once and return each word with its position and confidence."""
    pytesseract.pytesseract.tesseract_cmd = cfg["tesseract_cmd"]
    extraction = cfg["extraction"]
    data = pytesseract.image_to_data(
        image,
        lang=extraction["lang"],
        config=f"--psm {extraction['psm']}",
        output_type=pytesseract.Output.DICT,
    )
    keep = ("left", "top", "width", "height", "conf")
    words = []
    for index, text in enumerate(data["text"]):
        if text.strip() and float(data["conf"][index]) >= 0:
            word = {key: int(float(data[key][index])) for key in keep}
            word["text"] = text.strip()
            word["line"] = (
                f"{data['block_num'][index]}.{data['par_num'][index]}.{data['line_num'][index]}"
            )
            words.append(word)
    return words


def words_to_text(words: list[dict], page_width: int, right_zone: float) -> str:
    """Rebuild lines from words. Marks and CO cells at the far right go after a tab."""
    lines: dict[str, list[dict]] = {}
    for word in words:
        lines.setdefault(word["line"], []).append(word)
    output = []
    for line_words in lines.values():
        body, right = [], []
        for word in sorted(line_words, key=lambda w: w["left"]):
            in_zone = word["left"] >= right_zone * page_width
            (right if in_zone and RIGHT_CELL.match(word["text"]) else body).append(word["text"])
        output.append(" ".join(body) + ("\t" + " ".join(right) if right else ""))
    return "\n".join(output)


def mean_confidence(words: list[dict]) -> float | None:
    """Return the average Tesseract confidence of the words, or None if there are none."""
    return round(sum(word["conf"] for word in words) / len(words), 1) if words else None


def is_table_page(text: str, digit_ratio: float = 0.6, min_tokens: int = 30) -> bool:
    """Return True if a page is a statistical table (mostly digits in a grid)."""
    tokens = text.split()
    if len(tokens) < min_tokens:
        return False
    digits = sum(bool(re.fullmatch(r"[\d.,\-]*\d[\d.,\-]*", token)) for token in tokens)
    return digits / len(tokens) >= digit_ratio


def extract_text(pdf_path: Path, cfg: dict) -> list[PageText]:
    """Return the text of each page, using OCR when a page has no usable text layer."""
    extraction = cfg["extraction"]
    pages = []
    with pdfplumber.open(pdf_path) as plumber, pymupdf.open(pdf_path) as doc:
        for index, plumber_page in enumerate(plumber.pages):
            layer_text = (plumber_page.extract_text() or "").strip()
            if len(layer_text) >= extraction["min_chars_per_page"]:
                text, words, ocr_used, used = layer_text, [], False, None
            else:
                used = page_method(doc, index, extraction["method"])
                image = render_page(doc, index, used, extraction["dpi"])
                words = ocr_words(image, cfg)
                if used == "layers":
                    otsu_image = render_page(doc, index, "otsu", extraction["dpi"])
                    otsu_words = ocr_words(otsu_image, cfg)
                    if not keep_layers(
                        len(words),
                        len(otsu_words),
                        extraction["layers_min_word_ratio"],
                        extraction["layers_check_min_words"],
                    ):
                        image, words, used = otsu_image, otsu_words, "otsu-fallback"
                text = words_to_text(words, image.shape[1], extraction["right_zone"])
                ocr_used = True
            pages.append(
                PageText(
                    page_no=index + 1,
                    text=text,
                    has_text_layer=not ocr_used,
                    ocr_used=ocr_used,
                    is_table=is_table_page(
                        text, extraction["table_digit_ratio"], extraction["table_min_tokens"]
                    ),
                    mean_conf=mean_confidence(words),
                    words=words,
                    render_method=used,
                )
            )
    return pages


def paper_text(pages: list[PageText]) -> str:
    """Join a paper's pages into one text, leaving out statistical table pages."""
    return "\n".join(page.text for page in pages if not page.is_table)


def paper_confidence(pages: list[PageText]) -> float | None:
    """Return the average OCR confidence over a paper's pages that used OCR."""
    words = [word for page in pages if not page.is_table for word in page.words]
    return mean_confidence(words)


def cache_path(paper_id: str, ocr_dir: Path) -> Path:
    """Return the cache file for one paper: data/ocr/<paper_id>.json."""
    return ocr_dir / f"{paper_id}.json"


def save_cache(paper_id: str, method: str, pages: list[PageText], ocr_dir: Path) -> None:
    """Save a paper's pages, replacing the file in one step so a crash can't truncate it."""
    ocr_dir.mkdir(parents=True, exist_ok=True)
    path = cache_path(paper_id, ocr_dir)
    temp = path.with_name(path.name + ".tmp")
    record = {"paper_id": paper_id, "method": method, "pages": [asdict(page) for page in pages]}
    temp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def load_cache(paper_id: str, ocr_dir: Path, method: str) -> list[PageText] | None:
    """Return cached pages made with this method, or None if there are none."""
    path = cache_path(paper_id, ocr_dir)
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if record["method"] != method:
        return None
    return [PageText(**page) for page in record["pages"]]


def load_pages(paper_id: str, cfg: dict) -> list[PageText] | None:
    """Return a paper's cached pages, re-checking table pages against the current settings."""
    extraction = cfg["extraction"]
    pages = load_cache(paper_id, Path(cfg["paths"]["ocr"]), extraction["method"])
    if pages is None:
        return None
    for page in pages:
        page.is_table = is_table_page(
            page.text, extraction["table_digit_ratio"], extraction["table_min_tokens"]
        )
    return pages


def extract_cached(pdf_path: Path, paper_id: str, cfg: dict) -> list[PageText]:
    """Return a paper's pages from the cache, running OCR only the first time."""
    ocr_dir = Path(cfg["paths"]["ocr"])
    method = cfg["extraction"]["method"]
    pages = load_cache(paper_id, ocr_dir, method)
    if pages is None:
        pages = extract_text(pdf_path, cfg)
        save_cache(paper_id, method, pages, ocr_dir)
    return pages


def normalize_for_cer(text: str) -> str:
    """Drop table-rule characters and collapse whitespace, keeping case and everything else."""
    return " ".join(re.sub(r"[|_]", " ", text).split())


def character_error_rate(reference: str, hypothesis: str) -> float:
    """Return Levenshtein distance divided by the length of the reference text."""
    if not reference:
        raise ValueError("The reference text is empty")
    previous = list(range(len(hypothesis) + 1))
    for row, ref_char in enumerate(reference, start=1):
        current = [row]
        for column, hyp_char in enumerate(hypothesis, start=1):
            cost = 0 if ref_char == hyp_char else 1
            current.append(min(previous[column] + 1, current[column - 1] + 1, previous[column - 1] + cost))
        previous = current
    return previous[-1] / len(reference)
