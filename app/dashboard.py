"""Dashboard pages (Phase 8): home, question bank, explain data, topics, trends, model report, upload.

Every page reads the database built by the pipeline (data/questioniq.db) or the saved
metrics, so what it shows always matches the reports.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask.typing import ResponseReturnValue
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from werkzeug.utils import secure_filename

from questioniq.db import Paper, Prediction, Question, Topic, get_engine
from questioniq.infer import analyse_paper, load_assets
from questioniq.scrape import is_pdf
from questioniq.trends import GRADES, difficulty_mix_by_year, topic_share_by_year

bp = Blueprint("dash", __name__)


def _cfg() -> dict:
    """Return the project config the app was built with."""
    return current_app.config["QIQ"]


def _session() -> Session | None:
    """Return a database session, or None if the pipeline hasn't built the database yet."""
    path = Path(_cfg()["paths"]["db"])
    return Session(get_engine(path)) if path.exists() else None


def _no_database() -> ResponseReturnValue:
    """Explain that the database is missing and how to build it."""
    return render_template("message.html", title="No database yet",
                           body="Run scripts/run_pipeline.py once to build data/questioniq.db."), 503


def _metric(name: str) -> dict | None:
    """Return a saved metrics file from reports/metrics, or None if it doesn't exist yet."""
    path = Path(_cfg()["paths"]["metrics"]) / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def explanation_dict(question: Question, paper: Paper, prediction: Prediction | None,
                     topic: Topic | None) -> dict:
    """Return everything the Explain drawer shows for one stored question."""
    result = {
        "question_id": question.question_key, "course": paper.course, "year": paper.year,
        "exam_type": paper.exam_type, "qno": question.qno, "sub_part": question.sub_part,
        "text": question.text, "owner_label": question.owner_label,
        "topic_name": topic.name if topic else None,
    }
    if prediction is not None:
        result.update({
            "predicted": prediction.predicted,
            "probabilities": {"Easy": prediction.p_easy, "Medium": prediction.p_medium, "Hard": prediction.p_hard},
            "because": prediction.because,
            "reasons": json.loads(prediction.reasons_json),
            "topics": json.loads(prediction.topics_json),
            "outside_training_subjects": prediction.outside_training_subjects,
        })
    return result


def _base_query() -> Select:
    """Return the query joining each question with its paper, prediction and main topic."""
    return (select(Question, Paper, Prediction, Topic)
            .join(Paper, Question.paper_id == Paper.id)
            .outerjoin(Prediction, Prediction.question_id == Question.id)
            .outerjoin(Topic, Topic.id == Question.dominant_topic))


def apply_filters(query: Select, filters: dict) -> Select:
    """Narrow the question query by the filters that are set.

    Empty values are ignored, and so are topic or year values that aren't whole numbers.
    """
    if filters.get("department"):
        query = query.where(Paper.department == filters["department"])
    if filters.get("course"):
        query = query.where(Paper.course == filters["course"])
    if filters.get("topic", "").isdigit():
        query = query.where(Question.dominant_topic == int(filters["topic"]))
    if filters.get("difficulty"):
        query = query.where(Prediction.predicted == filters["difficulty"])
    if filters.get("year", "").isdigit():
        query = query.where(Paper.year == int(filters["year"]))
    if filters.get("exam_type"):
        query = query.where(Paper.exam_type == filters["exam_type"])
    if filters.get("q"):
        query = query.where(Question.text.ilike(f"%{filters['q']}%"))
    return query


@bp.get("/")
def home() -> ResponseReturnValue:
    """Show the totals and links to every page."""
    session = _session()
    if session is None:
        return _no_database()
    with session:
        totals = {
            "papers": session.scalar(select(func.count()).select_from(Paper)),
            "questions": session.scalar(select(func.count()).select_from(Question)),
            "courses": session.scalar(select(func.count(func.distinct(Paper.course)))),
            "departments": session.scalar(select(func.count(func.distinct(Paper.department)))),
            "years": sorted(year for year in session.scalars(select(func.distinct(Paper.year))) if year),
            "topics": session.scalar(select(func.count()).select_from(Topic)),
        }
    return render_template("home.html", totals=totals, difficulty=_metric("difficulty"))


@bp.get("/questions")
def questions() -> ResponseReturnValue:
    """Show the question bank with filters, keyword search and pages of 50."""
    session = _session()
    if session is None:
        return _no_database()
    filters = {key: request.args.get(key, "").strip()
               for key in ("department", "course", "topic", "difficulty", "year", "exam_type", "q")}
    page = max(request.args.get("page", 1, type=int), 1)
    size = _cfg()["dashboard"]["page_size"]
    with session:
        query = apply_filters(_base_query(), filters)
        total = session.scalar(select(func.count()).select_from(query.subquery()))
        rows = session.execute(query.order_by(Paper.year.desc(), Paper.id, Question.id)
                               .offset((page - 1) * size).limit(size)).all()
        options = {
            "department": sorted(session.scalars(select(func.distinct(Paper.department)))),
            "course": sorted(session.scalars(select(func.distinct(Paper.course)))),
            "year": sorted((y for y in session.scalars(select(func.distinct(Paper.year))) if y), reverse=True),
            "exam_type": sorted(session.scalars(select(func.distinct(Paper.exam_type)))),
            "topic": session.execute(select(Topic.id, Topic.name).order_by(Topic.id)).all(),
        }
        items = [explanation_dict(*row) for row in rows]
    pages = max((total + size - 1) // size, 1)
    return render_template("questions.html", items=items, filters=filters, options=options, total=total,
                           page=page, pages=pages, grades=GRADES)


@bp.get("/api/explain/<question_key>")
def explain(question_key: str) -> ResponseReturnValue:
    """Return one question's prediction, reasons and topics as JSON, for the Explain drawer."""
    session = _session()
    if session is None:
        abort(503)
    with session:
        row = session.execute(_base_query().where(Question.question_key == question_key)).first()
        if row is None:
            abort(404)
        return jsonify(explanation_dict(*row))


@bp.get("/topics")
def topics() -> ResponseReturnValue:
    """Show each topic with its keywords, question count and the departments it draws from."""
    session = _session()
    if session is None:
        return _no_database()
    with session:
        counts = session.execute(
            select(Question.dominant_topic, Paper.department, func.count())
            .join(Paper, Question.paper_id == Paper.id)
            .where(Question.dominant_topic.is_not(None))
            .group_by(Question.dominant_topic, Paper.department)
        ).all()
        listing = []
        for topic in session.scalars(select(Topic).order_by(Topic.id)):
            by_department = sorted(((dept, n) for t, dept, n in counts if t == topic.id), key=lambda item: -item[1])
            listing.append({"id": topic.id, "name": topic.name, "keywords": topic.keywords.split(),
                            "n_questions": sum(n for _, n in by_department), "departments": by_department[:4]})
    return render_template("topics.html", topics=listing, metrics=_metric("topics"))


def trend_frame(session: Session) -> pd.DataFrame:
    """Return one row per question with year, exam type, department, topic and difficulty."""
    rows = session.execute(
        select(Paper.year, Paper.exam_type, Paper.department, Question.dominant_topic,
               Prediction.predicted, Question.owner_label)
        .join(Paper, Question.paper_id == Paper.id)
        .outerjoin(Prediction, Prediction.question_id == Question.id)
    ).all()
    frame = pd.DataFrame(rows, columns=["year", "exam_type", "department", "dominant_topic", "predicted", "owner_label"])
    frame = frame.dropna(subset=["year"])
    frame["dominant_topic"] = frame["dominant_topic"].fillna(0).astype(int)
    return frame


@bp.get("/trends")
def trends() -> ResponseReturnValue:
    """Show topic share and difficulty mix by year, and the concepts that recur across years."""
    session = _session()
    if session is None:
        return _no_database()
    with session:
        frame = trend_frame(session)
        names = dict(session.execute(select(Topic.id, Topic.name)).all())
    shares = topic_share_by_year(frame.assign(exam_type="All"))
    years = sorted(shares["year"].unique().tolist())
    totals = shares.groupby("year")["year_total"].first().to_dict()
    topic_series = [{"label": names.get(int(topic), f"Topic {topic}"),
                     "data": [round(float(group.set_index("year")["share"].get(year, 0)) * 100, 1) for year in years]}
                    for topic, group in shares.groupby("topic")]
    trained = frame[frame["department"].isin(_cfg()["annotation"]["departments"])]
    mix = difficulty_mix_by_year(trained, "predicted")
    owner_mix = difficulty_mix_by_year(frame, "owner_label")
    concepts_path = Path(_cfg()["paths"]["trends"]) / "recurring_concepts.csv"
    concepts = list(csv.DictReader(open(concepts_path, encoding="utf-8")))[:40] if concepts_path.exists() else []
    chart = {
        "years": [f"{year} (n={totals[year]})" for year in years],
        "topics": topic_series,
        "mix_years": [f"{int(row.year)} (n={int(row.n_questions)})" for row in mix.itertuples()],
        "mix": {grade: [round(float(value) * 100, 1) for value in mix[grade]] for grade in GRADES},
    }
    return render_template("trends.html", chart=chart, owner_mix=owner_mix.to_dict("records"),
                           mix=mix.to_dict("records"), concepts=concepts, grades=GRADES)


@bp.get("/report")
def report() -> ResponseReturnValue:
    """Show every evaluation number, read from the saved metrics."""
    metrics = {name: _metric(name) for name in
               ("ocr", "segmentation", "preprocess", "topics", "difficulty", "explain", "explain_check", "kappa")}
    return render_template("report.html", m=metrics, grades=GRADES)


def _assets() -> dict:
    """Load the saved models for uploads once per app, on first use."""
    if "qiq_assets" not in current_app.extensions:
        current_app.extensions["qiq_assets"] = load_assets(_cfg())
    return current_app.extensions["qiq_assets"]


@bp.route("/upload", methods=["GET", "POST"])
def upload() -> ResponseReturnValue:
    """Take a PDF, analyse it with the saved models and show its questions with explanations."""
    if request.method == "GET":
        return render_template("upload.html", result=None, error=None)
    file = request.files.get("paper")
    data = file.read() if file else b""
    if not data or not is_pdf(data):
        return render_template("upload.html", result=None, error="Please choose a PDF file."), 400
    folder = Path(_cfg()["paths"]["uploads"])
    folder.mkdir(parents=True, exist_ok=True)
    name = secure_filename(file.filename or "paper.pdf") or "paper.pdf"
    path = folder / f"{datetime.now():%Y%m%d-%H%M%S}_{name}"
    path.write_bytes(data)
    result = analyse_paper(path, _cfg(), _assets())
    result["filename"] = file.filename
    result["departments"] = _assets()["departments"]
    return render_template("upload.html", result=result, error=None)
