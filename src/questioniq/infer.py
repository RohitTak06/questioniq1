"""Analyse one new paper with the saved models (Phase 8, the Upload page).

The same steps as the pipeline, for one PDF: extract (with OCR), segment, clean, topic
shares from the saved topic model, features, difficulty from the saved Random Forest, and
SHAP reasons. Nothing is retrained and nothing is added to the database.
"""

import json
import time
from pathlib import Path

import joblib

from questioniq.annotate import read_rows
from questioniq.explain import explain_rows, topic_explanation
from questioniq.extract import extract_text, paper_text
from questioniq.features import feature_table, load_bloom_verbs
from questioniq.preprocess import clean_question
from questioniq.segment import segment
from questioniq.topics import dominant_topics, topic_distribution


def load_assets(cfg: dict) -> dict:
    """Load everything an upload needs once: both saved models, word lists and topic names."""
    paths = cfg["paths"]
    topic_kind = json.loads((Path(paths["metrics"]) / "topics.json").read_text(encoding="utf-8"))["chosen_model"]
    topic_model = joblib.load(Path(paths["models"]) / f"topics_{topic_kind}.joblib")
    forest = joblib.load(Path(paths["models"]) / "difficulty_random_forest.joblib")
    verbs, phrases = load_bloom_verbs(Path(paths["bloom_verbs"]))
    keywords = [row["keywords"].split() for row in read_rows(Path(paths["topic_keywords"]))
                if row["model"] == topic_kind]
    names = {int(row["topic"]): row["name"].strip() for row in read_rows(Path(paths["topic_names"]))
             if row.get("name", "").strip()}
    return {
        "topic_model": topic_model["model"],
        "topic_vectorizer": topic_model["vectorizer"],
        "k": topic_model["k"],
        "forest": forest["model"],
        "features": forest["features"],
        "technical": set(forest["technical_terms"]),
        "departments": forest["departments"],
        "verbs": verbs,
        "phrases": phrases,
        "keywords": keywords,
        "topic_names": names,
        "stopwords": set(cfg["preprocess"]["exam_stopwords"]),
        "min_length": cfg["preprocess"]["min_token_length"],
    }


def analyse_paper(pdf_path: Path, cfg: dict, assets: dict) -> dict:
    """Return an uploaded paper's questions, each with its predicted difficulty and reasons.

    Also returns the time taken and how many pages needed OCR, for the 10-second target.
    """
    start = time.time()
    pages = extract_text(Path(pdf_path), cfg)
    questions = segment(paper_text(pages))
    rows = [
        {
            "question_id": f"upload-{number}",
            "text": question.text,
            "clean_text": clean_question(question.text, assets["stopwords"], assets["min_length"]),
            "marks": "" if question.marks is None else str(question.marks),
        }
        for number, question in enumerate(questions, start=1)
    ]
    results = []
    if rows:
        cleaned = [row["clean_text"] for row in rows]
        shares = topic_distribution(assets["topic_model"], assets["topic_vectorizer"], cleaned)
        dominant = dict(zip([row["question_id"] for row in rows], dominant_topics(shares)))
        table = feature_table(rows, dominant, assets["k"], assets["verbs"], assets["phrases"], assets["technical"])
        X = table.set_index("question_id")[assets["features"]]
        explanations = explain_rows(assets["forest"], X, 5, assets["topic_names"])
        for question, row, distribution, explanation in zip(questions, rows, shares, explanations):
            explanation["topics"] = topic_explanation(row["clean_text"].split(), list(distribution),
                                                      assets["keywords"], assets["topic_names"])
            results.append({
                **explanation,
                "qno": question.qno,
                "sub_part": question.sub_part,
                "alternative": question.alternative,
                "marks": question.marks,
                "text": question.text,
            })
    return {
        "questions": results,
        "n_pages": len(pages),
        "n_ocr_pages": sum(page.ocr_used for page in pages),
        "seconds": round(time.time() - start, 1),
    }
