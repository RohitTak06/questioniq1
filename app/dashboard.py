"""Dashboard pages (Phase 8): home, question bank, explain data, topics, trends, model report, upload.

Every page reads the database built by the pipeline (data/questioniq.db) or the saved
metrics, so what it shows always matches the reports.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from flask import Blueprint, abort, current_app, jsonify, render_template, request, session as flask_session, redirect, url_for
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


BTECH_DEPTS = ["CS", "AS", "EE", "ME", "CE", "CC", "ES", "MA"]
BBA_DEPTS = ["FA", "ED", "OP", "BS", "LS", "IL", "LD", "ID"]

DEPT_NAMES = {
    "CS": "Computer Science & Engineering",
    "AS": "Applied Sciences",
    "EE": "Electrical & Electronics Engineering",
    "ME": "Mechanical Engineering",
    "CE": "Civil Engineering",
    "CC": "Chemical & Cloud Computing",
    "ES": "Environmental Studies",
    "MA": "Mathematics",
    "FA": "Finance & Accounting",
    "ED": "Entrepreneurship & Innovation",
    "OP": "Operations & Supply Chain",
    "BS": "Business Studies",
    "LS": "Legal Studies & Ethics",
    "IL": "International Law & Relations",
    "LD": "Leadership & Development",
    "ID": "Interdisciplinary Studies",
}


def _get_program() -> str:
    """Get active program from request arg or session, defaulting to 'btech'."""
    prog = request.args.get("program")
    if prog in ("btech", "bba", "all"):
        flask_session["program"] = prog
    return flask_session.get("program", "btech")


def explanation_dict(question: Question, paper: Paper, prediction: Prediction | None,
                     topic: Topic | None) -> dict:
    """Return everything the Explain drawer shows for one stored question."""
    result = {
        "question_id": question.question_key, "course": paper.course, "year": paper.year,
        "department": paper.department, "exam_type": paper.exam_type,
        "qno": question.qno, "sub_part": question.sub_part,
        "marks": question.marks, "text": question.text, "owner_label": question.owner_label,
        "topic_name": topic.name if topic else None,
    }
    if prediction is not None:
        result.update({
            "predicted": prediction.predicted,
            "probabilities": {"Easy": prediction.p_easy, "Medium": prediction.p_medium, "Hard": prediction.p_hard},
            "because": prediction.because,
            "reasons": json.loads(prediction.reasons_json) if prediction.reasons_json else [],
            "topics": json.loads(prediction.topics_json) if prediction.topics_json else {},
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
    program = filters.get("program")
    if program == "btech":
        query = query.where(Paper.department.in_(BTECH_DEPTS))
    elif program == "bba":
        query = query.where(Paper.department.in_(BBA_DEPTS))

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
    """Show the unified QuestionIQ Landing Page (Screen 1 in wireframe)."""
    if request.args.get("view") == "dashboard" or request.args.get("program"):
        return dashboard()

    db_session = _session()
    if db_session is None:
        return _no_database()

    with db_session:
        totals = {
            "papers": db_session.scalar(select(func.count()).select_from(Paper)),
            "questions": db_session.scalar(select(func.count()).select_from(Question)),
            "courses": db_session.scalar(select(func.count(func.distinct(Paper.course)))),
            "topics": db_session.scalar(select(func.count()).select_from(Topic)),
        }
    return render_template("landing.html", totals=totals)


@bp.get("/dashboard")
def dashboard() -> ResponseReturnValue:
    """Show the interactive Dashboard (Screen 2)."""
    db_session = _session()
    if db_session is None:
        return _no_database()

    program = _get_program()
    dept_filter = None
    if program == "btech":
        dept_filter = Paper.department.in_(BTECH_DEPTS)
    elif program == "bba":
        dept_filter = Paper.department.in_(BBA_DEPTS)

    with db_session:
        q_papers_cnt = select(func.count()).select_from(Paper)
        q_quest_cnt = select(func.count()).select_from(Question).join(Paper, Question.paper_id == Paper.id)
        q_courses_cnt = select(func.count(func.distinct(Paper.course)))
        q_depts_cnt = select(func.count(func.distinct(Paper.department)))
        q_years = select(func.distinct(Paper.year))

        if dept_filter is not None:
            q_papers_cnt = q_papers_cnt.where(dept_filter)
            q_quest_cnt = q_quest_cnt.where(dept_filter)
            q_courses_cnt = q_courses_cnt.where(dept_filter)
            q_depts_cnt = q_depts_cnt.where(dept_filter)
            q_years = q_years.where(dept_filter)

        totals = {
            "papers": db_session.scalar(q_papers_cnt),
            "questions": db_session.scalar(q_quest_cnt),
            "courses": db_session.scalar(q_courses_cnt),
            "departments": db_session.scalar(q_depts_cnt),
            "years": sorted(year for year in db_session.scalars(q_years) if year),
            "topics": db_session.scalar(select(func.count()).select_from(Topic)),
        }

        # Questions by Year
        y_query = (select(Paper.year, func.count(Question.id))
                   .join(Question, Question.paper_id == Paper.id)
                   .where(Paper.year.is_not(None)))
        if dept_filter is not None:
            y_query = y_query.where(dept_filter)
        y_rows = db_session.execute(y_query.group_by(Paper.year).order_by(Paper.year)).all()
        by_year = [{"year": str(y), "count": count} for y, count in y_rows]

        # Difficulty Distribution
        d_query = (select(Prediction.predicted, func.count(Question.id))
                   .join(Question, Prediction.question_id == Question.id)
                   .join(Paper, Question.paper_id == Paper.id)
                   .where(Prediction.predicted.is_not(None)))
        if dept_filter is not None:
            d_query = d_query.where(dept_filter)
        d_counts = dict(db_session.execute(d_query.group_by(Prediction.predicted)).all())
        total_d = sum(d_counts.values()) or 1
        diff_dist = {
            "Easy": d_counts.get("Easy", 0),
            "Medium": d_counts.get("Medium", 0),
            "Hard": d_counts.get("Hard", 0),
            "total": total_d,
            "pct_easy": round((d_counts.get("Easy", 0) / total_d) * 100, 1),
            "pct_medium": round((d_counts.get("Medium", 0) / total_d) * 100, 1),
            "pct_hard": round((d_counts.get("Hard", 0) / total_d) * 100, 1),
        }

        # Top 5 Topics
        t_query = (select(Topic.name, func.count(Question.id))
                   .join(Question, Question.dominant_topic == Topic.id)
                   .join(Paper, Question.paper_id == Paper.id))
        if dept_filter is not None:
            t_query = t_query.where(dept_filter)
        t_rows = db_session.execute(t_query.group_by(Topic.name).order_by(func.count(Question.id).desc()).limit(5)).all()
        top_topics = [{"name": name, "count": count, "pct": round((count / (totals["questions"] or 1)) * 100, 1)}
                      for name, count in t_rows]

        # Recent preview questions
        prev_query = _base_query()
        if dept_filter is not None:
            prev_query = prev_query.where(dept_filter)
        prev_rows = db_session.execute(prev_query.order_by(Paper.year.desc(), Question.id).limit(6)).all()
        preview_questions = [explanation_dict(*r) for r in prev_rows]

    return render_template("dashboard.html", totals=totals, difficulty=_metric("difficulty"),
                           program=program, by_year=by_year, diff_dist=diff_dist,
                           top_topics=top_topics, preview_questions=preview_questions)


@bp.get("/subjects")
def subjects() -> ResponseReturnValue:
    """Show the Subject & Department Directory (Screen 3 in collage)."""
    db_session = _session()
    if db_session is None:
        return _no_database()

    program = _get_program()
    dept_filter = None
    if program == "btech":
        dept_filter = Paper.department.in_(BTECH_DEPTS)
    elif program == "bba":
        dept_filter = Paper.department.in_(BBA_DEPTS)

    with db_session:
        query = (select(Paper.department, Paper.course, func.count(Question.id), func.count(func.distinct(Paper.id)))
                 .join(Question, Question.paper_id == Paper.id))
        if dept_filter is not None:
            query = query.where(dept_filter)
        rows = db_session.execute(query.group_by(Paper.department, Paper.course).order_by(Paper.department, Paper.course)).all()

        departments = {}
        for dept, course, q_count, p_count in rows:
            if dept not in departments:
                departments[dept] = {
                    "code": dept,
                    "name": DEPT_NAMES.get(dept, dept),
                    "courses": [],
                    "total_questions": 0,
                    "total_papers": 0,
                }
            departments[dept]["courses"].append({
                "code": course,
                "questions": q_count,
                "papers": p_count
            })
            departments[dept]["total_questions"] += q_count
            departments[dept]["total_papers"] += p_count

        dept_list = sorted(departments.values(), key=lambda d: -d["total_questions"])
        summary = {
            "total_departments": len(dept_list),
            "total_courses": sum(len(d["courses"]) for d in dept_list),
            "total_questions": sum(d["total_questions"] for d in dept_list),
            "total_papers": sum(d["total_papers"] for d in dept_list),
        }

    return render_template("subjects.html", departments=dept_list, summary=summary, program=program)


@bp.get("/difficulty")
def difficulty() -> ResponseReturnValue:
    """Show Difficulty Analysis (Screen 9 in wireframe)."""
    db_session = _session()
    if db_session is None:
        return _no_database()

    program = _get_program()
    dept_filter = None
    if program == "btech":
        dept_filter = Paper.department.in_(BTECH_DEPTS)
    elif program == "bba":
        dept_filter = Paper.department.in_(BBA_DEPTS)

    with db_session:
        # Overall difficulty
        d_query = (select(Prediction.predicted, func.count(Question.id))
                   .join(Question, Prediction.question_id == Question.id)
                   .join(Paper, Question.paper_id == Paper.id)
                   .where(Prediction.predicted.is_not(None)))
        if dept_filter is not None:
            d_query = d_query.where(dept_filter)
        d_counts = dict(db_session.execute(d_query.group_by(Prediction.predicted)).all())
        total_d = sum(d_counts.values()) or 1
        diff_dist = {
            "Easy": d_counts.get("Easy", 0),
            "Medium": d_counts.get("Medium", 0),
            "Hard": d_counts.get("Hard", 0),
            "total": total_d,
            "pct_easy": round((d_counts.get("Easy", 0) / total_d) * 100, 1),
            "pct_medium": round((d_counts.get("Medium", 0) / total_d) * 100, 1),
            "pct_hard": round((d_counts.get("Hard", 0) / total_d) * 100, 1),
        }

        # Breakdown by department
        dept_diff_query = (select(Paper.department, Prediction.predicted, func.count(Question.id))
                           .join(Question, Prediction.question_id == Question.id)
                           .join(Paper, Question.paper_id == Paper.id)
                           .where(Prediction.predicted.is_not(None)))
        if dept_filter is not None:
            dept_diff_query = dept_diff_query.where(dept_filter)
        dept_diff_rows = db_session.execute(dept_diff_query.group_by(Paper.department, Prediction.predicted)).all()
        dept_breakdown = {}
        for dept, pred, count in dept_diff_rows:
            if dept not in dept_breakdown:
                dept_breakdown[dept] = {"dept": dept, "name": DEPT_NAMES.get(dept, dept), "Easy": 0, "Medium": 0, "Hard": 0, "total": 0}
            dept_breakdown[dept][pred] = count
            dept_breakdown[dept]["total"] += count

        dept_diff_list = sorted(dept_breakdown.values(), key=lambda x: -x["total"])[:8]
        for d in dept_diff_list:
            tot = d["total"] or 1
            d["pct_easy"] = round((d["Easy"] / tot) * 100, 1)
            d["pct_medium"] = round((d["Medium"] / tot) * 100, 1)
            d["pct_hard"] = round((d["Hard"] / tot) * 100, 1)

    metric_data = _metric("difficulty")
    return render_template("difficulty.html", diff_dist=diff_dist, dept_diff=dept_diff_list,
                           metric=metric_data, program=program)


@bp.get("/explain/<question_key>")
def explain_page(question_key: str) -> ResponseReturnValue:
    """Dedicated full-page view for Question Analysis & Explanation (Screen 4 / 6)."""
    db_session = _session()
    if db_session is None:
        abort(503)
    with db_session:
        row = db_session.execute(_base_query().where(Question.question_key == question_key)).first()
        if row is None:
            abort(404)
        item = explanation_dict(*row)
    return render_template("explain.html", item=item, program=_get_program())


@bp.get("/questions")
def questions() -> ResponseReturnValue:
    """Show the question bank with filters, keyword search and pages of 50."""
    db_session = _session()
    if db_session is None:
        return _no_database()

    prog_default = _get_program()
    filters = {key: request.args.get(key, "").strip()
               for key in ("department", "course", "topic", "difficulty", "year", "exam_type", "q", "program")}
    if not filters.get("program"):
        filters["program"] = prog_default

    page = max(request.args.get("page", 1, type=int), 1)
    size = _cfg()["dashboard"]["page_size"]
    with db_session:
        query = apply_filters(_base_query(), filters)
        total = db_session.scalar(select(func.count()).select_from(query.subquery()))
        rows = db_session.execute(query.order_by(Paper.year.desc(), Paper.id, Question.id)
                               .offset((page - 1) * size).limit(size)).all()

        dept_query = select(func.distinct(Paper.department))
        if filters.get("program") == "btech":
            dept_query = dept_query.where(Paper.department.in_(BTECH_DEPTS))
        elif filters.get("program") == "bba":
            dept_query = dept_query.where(Paper.department.in_(BBA_DEPTS))

        course_query = select(func.distinct(Paper.course))
        if filters.get("program") == "btech":
            course_query = course_query.where(Paper.department.in_(BTECH_DEPTS))
        elif filters.get("program") == "bba":
            course_query = course_query.where(Paper.department.in_(BBA_DEPTS))

        options = {
            "department": sorted(db_session.scalars(dept_query)),
            "course": sorted(db_session.scalars(course_query)),
            "year": sorted((y for y in db_session.scalars(select(func.distinct(Paper.year))) if y), reverse=True),
            "exam_type": sorted(db_session.scalars(select(func.distinct(Paper.exam_type)))),
            "topic": db_session.execute(select(Topic.id, Topic.name).order_by(Topic.id)).all(),
        }
        items = [explanation_dict(*row) for row in rows]
    pages = max((total + size - 1) // size, 1)
    return render_template("questions.html", items=items, filters=filters, options=options, total=total,
                           page=page, pages=pages, grades=GRADES, program=filters["program"])


@bp.get("/api/explain/<question_key>")
def explain(question_key: str) -> ResponseReturnValue:
    """Return one question's prediction, reasons and topics as JSON, for the Explain drawer/modal."""
    db_session = _session()
    if db_session is None:
        abort(503)
    with db_session:
        row = db_session.execute(_base_query().where(Question.question_key == question_key)).first()
        if row is None:
            abort(404)
        return jsonify(explanation_dict(*row))


@bp.get("/topics")
def topics() -> ResponseReturnValue:
    """Show each topic with its keywords, question count, departments, and summary strip."""
    db_session = _session()
    if db_session is None:
        return _no_database()

    program = _get_program()
    dept_filter = None
    if program == "btech":
        dept_filter = Paper.department.in_(BTECH_DEPTS)
    elif program == "bba":
        dept_filter = Paper.department.in_(BBA_DEPTS)

    with db_session:
        counts_query = (
            select(Question.dominant_topic, Paper.department, func.count())
            .join(Paper, Question.paper_id == Paper.id)
            .where(Question.dominant_topic.is_not(None))
        )
        if dept_filter is not None:
            counts_query = counts_query.where(dept_filter)
        counts = db_session.execute(counts_query.group_by(Question.dominant_topic, Paper.department)).all()

        total_depts_q = select(func.count(func.distinct(Paper.department)))
        total_papers_q = select(func.count(func.distinct(Paper.id)))
        if dept_filter is not None:
            total_depts_q = total_depts_q.where(dept_filter)
            total_papers_q = total_papers_q.where(dept_filter)

        total_depts = db_session.scalar(total_depts_q)
        total_papers = db_session.scalar(total_papers_q)

        listing = []
        for topic in db_session.scalars(select(Topic).order_by(Topic.id)):
            by_department = sorted(((dept, n) for t, dept, n in counts if t == topic.id), key=lambda item: -item[1])
            q_sum = sum(n for _, n in by_department)
            listing.append({
                "id": topic.id,
                "name": topic.name,
                "keywords": topic.keywords.split(),
                "n_questions": q_sum,
                "departments": by_department[:4]
            })

        total_mapped = sum(t["n_questions"] for t in listing)
        active_topics = len([t for t in listing if t["n_questions"] > 0])

        topic_metrics = _metric("topics") or {}
        summary = {
            "total_topics": len(listing),
            "active_topics": active_topics,
            "total_questions": total_mapped,
            "total_departments": total_depts,
            "total_papers": total_papers,
        }

    return render_template("topics.html", topics=listing, summary=summary, metrics=topic_metrics, program=program)


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
