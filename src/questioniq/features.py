"""Turn a question into human-readable features for the difficulty model (Phase 5).

Every feature is something a person can check by reading the question, so the model's
explanations (Phase 6) make sense: its Bloom level, length, marks, number of parts,
numbers and formulas, rare technical words, and its main topic.
"""

import re
from pathlib import Path
from statistics import median

import numpy as np
import pandas as pd
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer

from questioniq.preprocess import tokenize, verb_lemma

SUB_PART = re.compile(r"(?:^|\s)\(?((?:[a-h])|(?:i{1,3}|iv|vi{0,3}|ix|x))\)\s", re.I)  # (a) b) (ii)
FORMULA = re.compile(r"[=^∫Σ∑√≤≥]|\b(?:integral|sigma|root|sqrt|derivative|log|lim)\b", re.I)
NUMBER = re.compile(r"\d")
BASE_FEATURES = [
    "bloom_level",
    "word_count",
    "marks",
    "marks_missing",
    "n_sub_parts",
    "has_numbers",
    "has_formula",
    "n_technical_terms",
]


def load_bloom_verbs(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Return the Bloom verb list as {verb: level} and {opening phrase: level}."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    verbs = {verb: int(level) for level, words in data["verbs"].items() for verb in words}
    phrases = {phrase: int(level) for level, items in data.get("phrases", {}).items() for phrase in items}
    return verbs, phrases


CLAUSE_BREAK = re.compile(r"[.?!;:]\s+|\(?\b(?:[a-h]|i{1,3}|iv|vi{0,3})\)\s+|\band\s+(?=[a-z]+\b)", re.I)
COMMAND_WINDOW = 3  # a command verb sits in the first few words of a sentence or part


def clauses(text: str) -> list[str]:
    """Split a question into sentences and parts: at . ? ; : and at (a), b), (ii)."""
    return [piece for piece in CLAUSE_BREAK.split(text) if piece and piece.strip()]


def bloom_level(text: str, verbs: dict[str, int], phrases: dict[str, int] | None = None) -> int:
    """Return the highest Bloom level among the question's command verbs, or 0 if none.

    Only verbs that start a sentence or part count ("Design a ...", "(b) Prove ..."),
    not verbs inside the question's story ("the company plans to ..."). Words are
    reduced to their verb form first, so "Proves" counts. An opening phrase such as
    "what is" also counts.
    """
    levels = []
    for clause in clauses(text):
        words = tokenize(clause)
        for word in words[:COMMAND_WINDOW]:
            form = verb_lemma(word)
            if form in verbs or word in verbs:
                levels.append(verbs.get(form, verbs.get(word)))
                break
        start = " ".join(words[:4])
        levels += [level for phrase, level in (phrases or {}).items() if start.startswith(phrase)]
    return max(levels, default=0)


def word_count(text: str) -> int:
    """Return the number of words in the raw question."""
    return len(text.split())


def count_sub_parts(text: str) -> int:
    """Return how many labelled parts the question has: (a), b), (ii) and so on."""
    return len({match.lower() for match in SUB_PART.findall(text)})


def has_numbers(text: str) -> int:
    """Return 1 if the question contains any digit (data to work with), else 0."""
    return int(bool(NUMBER.search(text)))


def has_formula(text: str) -> int:
    """Return 1 if the question has formula symbols or words (=, ^, integral, root...), else 0."""
    return int(bool(FORMULA.search(text)))


def technical_vocabulary(clean_docs: list[str], min_df: int = 2) -> set[str]:
    """Return the rare, specialised words: those with an IDF at or above the median.

    IDF is high for words that appear in few questions. Words in only one question are
    left out (min_df), since most of them are OCR errors rather than technical terms.
    The labels are never used here.
    """
    vectorizer = TfidfVectorizer(analyzer=str.split, min_df=min_df)
    vectorizer.fit(clean_docs)
    idf = vectorizer.idf_
    threshold = float(np.median(idf))
    return {word for word, value in zip(vectorizer.get_feature_names_out(), idf) if value >= threshold}


def n_technical_terms(clean_text: str, technical: set[str]) -> int:
    """Return how many different technical words a cleaned question uses."""
    return len(set(clean_text.split()) & technical)


def marks_value(raw: str) -> float | None:
    """Return the marks as a number, or None if the segmenter found none."""
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def topic_features(dominant_topic: int, k: int) -> dict[str, int]:
    """Return the main topic as k yes/no columns (topic_1 ... topic_k); all 0 if no topic."""
    return {f"topic_{number}": int(number == dominant_topic) for number in range(1, k + 1)}


def feature_table(
    rows: list[dict],
    dominant: dict[str, int],
    k: int,
    verbs: dict[str, int],
    phrases: dict[str, int],
    technical: set[str],
) -> pd.DataFrame:
    """Return one row of features per question, keyed by question_id.

    Missing marks get the median of all found marks plus marks_missing = 1, so the model
    can tell an imputed value from a real one. The median uses every question, not labels.
    """
    found = [marks_value(row["marks"]) for row in rows]
    found = [value for value in found if value is not None]
    fill = median(found) if found else 0.0
    table = []
    for row in rows:
        marks = marks_value(row["marks"])
        features = {
            "question_id": row["question_id"],
            "bloom_level": bloom_level(row["text"], verbs, phrases),
            "word_count": word_count(row["text"]),
            "marks": marks if marks is not None else fill,
            "marks_missing": int(marks is None),
            "n_sub_parts": count_sub_parts(row["text"]),
            "has_numbers": has_numbers(row["text"]),
            "has_formula": has_formula(row["text"]),
            "n_technical_terms": n_technical_terms(row["clean_text"], technical),
        }
        features.update(topic_features(dominant.get(row["question_id"], 0), k))
        table.append(features)
    return pd.DataFrame(table)


def feature_names(k: int) -> list[str]:
    """Return the model's feature columns in order: the base features, then topic_1 ... topic_k."""
    return BASE_FEATURES + [f"topic_{number}" for number in range(1, k + 1)]
