"""Dashboard pages and the upload, on a fake database and small fake models."""

import copy
import io
import json
from pathlib import Path

import joblib
import pymupdf
import pytest
from sklearn.ensemble import RandomForestClassifier

from app import create_app
from questioniq.annotate import write_rows
from questioniq.config import load_config
from questioniq.db import build_database
from questioniq.features import feature_names, feature_table, load_bloom_verbs
from questioniq.topics import fit_nmf, top_keywords

ROOT = Path(__file__).resolve().parent.parent


def explanation(predicted: str, outside: bool) -> dict:
    return {"predicted": predicted, "probabilities": {"Easy": 0.2, "Medium": 0.2, "Hard": 0.6},
            "because": f"{predicted} because: fake reason", "reasons": [{"text": "fake reason", "shap": 0.1}],
            "topics": {"topics": [{"topic": 1, "name": "Fake trees", "share": 1.0, "keywords_found": ["tree"]}]},
            "outside_training_subjects": outside}


def sources() -> dict:
    papers = [{"paper_id": "7", "course": "CS1", "year": "2023", "exam_type": "Endterm", "path": "a.pdf"},
              {"paper_id": "8", "course": "ME1", "year": "2024", "exam_type": "Midterm", "path": "b.pdf"}]
    questions = [
        {"question_id": "7-1", "paper_id": "7", "qno": "1", "sub_part": "", "alternative": "0", "marks": "5",
         "co": "", "text": "Fake binary tree traversal question", "clean_text": "binary tree traversal"},
        {"question_id": "8-1", "paper_id": "8", "qno": "1", "sub_part": "", "alternative": "0", "marks": "",
         "co": "", "text": "Fake gear design question", "clean_text": "gear design"},
    ]
    return {"papers": papers, "departments": {"7": "CS", "8": "ME"}, "questions": questions,
            "topics": [{"topic": "1", "name": "Fake trees", "keywords": "tree binary_tree", "model": "nmf"},
                       {"topic": "2", "name": "Fake gears", "keywords": "gear", "model": "nmf"}],
            "shares": {"7-1": [1.0, 0.0], "8-1": [0.0, 1.0]},
            "explanations": {"7-1": explanation("Hard", False), "8-1": explanation("Easy", True)},
            "labels": {"7-1": "Hard"}}


DOCS = ["binary tree node traversal", "binary tree insert node", "matrix rank eigenvalue", "matrix vector rank",
        "router packet subnet", "router subnet protocol"] * 3


def make_models(tmp_path: Path) -> None:
    """Save a tiny topic model and forest, trained on made-up questions, where uploads expect them."""
    (tmp_path / "models").mkdir()
    topic_model, vectorizer = fit_nmf(DOCS, 3, 42)
    joblib.dump({"kind": "nmf", "k": 3, "model": topic_model, "vectorizer": vectorizer},
                tmp_path / "models" / "topics_nmf.joblib")
    keywords = top_keywords(topic_model, list(vectorizer.get_feature_names_out()), 3)
    write_rows(tmp_path / "topic_keywords.csv", [{"model": "nmf", "k": 3, "topic": n, "keywords": " ".join(words)}
               for n, words in enumerate(keywords, start=1)], ["model", "k", "topic", "keywords"])
    write_rows(tmp_path / "topic_names.csv", [{"model": "nmf", "k": 3, "topic": 1, "keywords": "", "name": "Fake trees"}],
               ["model", "k", "topic", "keywords", "name"])
    verbs, phrases = load_bloom_verbs(ROOT / "bloom_verbs.yaml")
    rows = [{"question_id": f"f-{n}", "text": f"Define {doc}" if n % 2 else f"Design {doc} [10]", "clean_text": doc,
             "marks": "2" if n % 2 else "10"} for n, doc in enumerate(DOCS)]
    table = feature_table(rows, {}, 3, verbs, phrases, {"eigenvalue", "subnet"})
    labels = ["Easy" if n % 2 else "Hard" for n in range(len(DOCS))]
    forest = RandomForestClassifier(n_estimators=20, random_state=42).fit(table[feature_names(3)], labels)
    joblib.dump({"model": forest, "features": feature_names(3), "technical_terms": ["eigenvalue", "subnet"],
                 "departments": ["CS", "AS"]}, tmp_path / "models" / "difficulty_random_forest.joblib")


@pytest.fixture
def client(tmp_path):
    cfg = copy.deepcopy(load_config())
    metrics = tmp_path / "metrics"
    metrics.mkdir()
    (metrics / "topics.json").write_text(json.dumps({
        "chosen_model": "nmf", "chosen_k": 2, "best": {"nmf": {"k": 2, "c_v": 0.5}, "lda": {"k": 3, "c_v": 0.4}},
        "sweep": [{"model": m, "k": k, "c_v": 0.4} for m in ("lda", "nmf") for k in (2, 3)],
        "subject_alignment": {"nmi": 0.2}}), encoding="utf-8")
    (metrics / "difficulty.json").write_text(json.dumps({
        "n_labelled": 2, "label_counts": {"Easy": 1, "Medium": 0, "Hard": 1}, "label_source": "round 1",
        "chosen_model": "random_forest",
        "results": {"random_forest": {"macro_f1_mean": 0.4, "macro_f1_std": 0.1, "accuracy": 0.5, "labels": ["Easy", "Medium", "Hard"],
                                      "per_class": {g: {"precision": 0.5, "recall": 0.5, "f1-score": 0.5} for g in ("Easy", "Medium", "Hard")},
                                      "confusion_matrix": [[1, 0, 0], [0, 0, 0], [0, 0, 1]]}}}), encoding="utf-8")
    cfg["paths"].update({"db": str(tmp_path / "q.db"), "metrics": str(metrics), "trends": str(tmp_path / "trends"),
                         "uploads": str(tmp_path / "uploads"), "models": str(tmp_path / "models"),
                         "topic_keywords": str(tmp_path / "topic_keywords.csv"),
                         "topic_names": str(tmp_path / "topic_names.csv"), "bloom_verbs": str(ROOT / "bloom_verbs.yaml")})
    build_database(sources(), tmp_path / "q.db")
    return create_app(cfg).test_client(), tmp_path


def page(client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == 200, url
    return response.get_data(as_text=True)


def test_every_page_loads(client) -> None:
    client, _ = client
    for url in ["/", "/questions", "/topics", "/trends", "/report", "/upload", "/label"]:
        page(client, url)


def test_home_shows_totals(client) -> None:
    client, _ = client
    html = page(client, "/")
    assert "<b>2</b>papers" in html and "<b>2023–2024</b>years" in html


@pytest.mark.parametrize(
    "query, shown, hidden",
    [
        ("", ["binary tree", "gear design"], []),
        ("?department=CS", ["binary tree"], ["gear design"]),
        ("?topic=2", ["gear design"], ["binary tree"]),
        ("?difficulty=Hard", ["binary tree"], ["gear design"]),
        ("?year=2024&exam_type=Midterm", ["gear design"], ["binary tree"]),
        ("?q=TRAVERSAL", ["binary tree"], ["gear design"]),
        ("?year=abc&topic=x", ["binary tree", "gear design"], []),  # bad values are ignored
    ],
)
def test_question_filters(client, query: str, shown: list[str], hidden: list[str]) -> None:
    client, _ = client
    html = page(client, f"/questions{query}")
    assert all(f"Fake {text}" in html for text in shown)
    assert not any(f"Fake {text}" in html for text in hidden)


def test_outside_subjects_get_a_grey_badge(client) -> None:
    client, _ = client
    html = page(client, "/questions?department=ME")
    assert 'class="badge outside"' in html


def test_explain_api_returns_the_drawer_data(client) -> None:
    client, _ = client
    data = client.get("/api/explain/7-1").get_json()
    assert data["predicted"] == "Hard" and data["owner_label"] == "Hard" and data["topic_name"] == "Fake trees"
    assert data["reasons"][0]["text"] == "fake reason"
    assert client.get("/api/explain/9-9").status_code == 404


def test_topics_and_report_read_the_database_and_metrics(client) -> None:
    client, _ = client
    assert "Fake gears" in page(client, "/topics")
    report = page(client, "/report")
    assert "random forest" in report and "after round 2" in report


def test_pages_explain_a_missing_database(client) -> None:
    client, tmp_path = client
    (tmp_path / "q.db").unlink()
    response = client.get("/questions")
    assert response.status_code == 503 and "run_pipeline.py" in response.get_data(as_text=True)


def test_upload_refuses_files_that_are_not_pdfs(client) -> None:
    client, _ = client
    response = client.post("/upload", data={"paper": (io.BytesIO(b"not a pdf"), "fake.pdf")},
                           content_type="multipart/form-data")
    assert response.status_code == 400 and "choose a PDF" in response.get_data(as_text=True)


def test_upload_analyses_a_paper_with_the_saved_models(client) -> None:
    client, tmp_path = client
    make_models(tmp_path)
    document = pymupdf.open()
    pdf_page = document.new_page()
    lines = ["Fake University End Term Examination Max. Marks: 12",
             "Q1. Define a binary tree and explain node traversal with an example. [2]",
             "Q2. Design a router subnet scheme for a fake campus network with eigenvalue checks. [10]"]
    for number, line in enumerate(lines):
        pdf_page.insert_text((40, 60 + 24 * number), line, fontsize=10)
    data = document.tobytes()
    response = client.post("/upload", data={"paper": (io.BytesIO(data), "fake paper.pdf")},
                           content_type="multipart/form-data")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "2 questions found" in html and "UPLOAD_RESULTS" in html
    assert list((tmp_path / "uploads").glob("*_fake_paper.pdf"))
