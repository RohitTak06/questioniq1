"""SQLite database for the dashboard (Phase 7).

The database is rebuilt from the pipeline's output files every time: papers, questions,
topics, each question's topic shares, and the difficulty predictions with their reasons.
It is written to a temporary file first and swapped in only when complete, so a failed
build never leaves a half-filled database behind.
"""

import json
import os
from pathlib import Path

from sqlalchemy import Boolean, Engine, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    """Base class for all database tables."""


class Paper(Base):
    """One downloaded exam paper."""

    __tablename__ = "papers"
    id: Mapped[int] = mapped_column(primary_key=True)  # the portal's paper ID
    course: Mapped[str] = mapped_column(String(20))
    course_name: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(4))
    year: Mapped[int | None] = mapped_column(Integer)
    exam_type: Mapped[str] = mapped_column(String(20))
    semester: Mapped[str] = mapped_column(String(20))
    path: Mapped[str] = mapped_column(String(300))
    n_pages: Mapped[int | None] = mapped_column(Integer)


class Question(Base):
    """One question extracted from a paper."""

    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_key: Mapped[str] = mapped_column(String(20), unique=True)  # such as 33-4
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"))
    qno: Mapped[str] = mapped_column(String(10))
    sub_part: Mapped[str] = mapped_column(String(10))
    alternative: Mapped[int] = mapped_column(Integer)
    marks: Mapped[float | None] = mapped_column(Float)
    co: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)
    clean_text: Mapped[str] = mapped_column(Text)
    dominant_topic: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    owner_label: Mapped[str | None] = mapped_column(String(10))  # round 1, or settled after round 2


class Topic(Base):
    """One discovered topic with its owner-given name."""

    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)  # topic number, from 1
    name: Mapped[str] = mapped_column(String(100))
    keywords: Mapped[str] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(10))


class QuestionTopic(Base):
    """A question's share of one topic."""

    __tablename__ = "question_topics"
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    share: Mapped[float] = mapped_column(Float)


class Prediction(Base):
    """One difficulty prediction for a question, with its explanation."""

    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), unique=True)
    model: Mapped[str] = mapped_column(String(30))
    predicted: Mapped[str] = mapped_column(String(10))
    p_easy: Mapped[float] = mapped_column(Float)
    p_medium: Mapped[float] = mapped_column(Float)
    p_hard: Mapped[float] = mapped_column(Float)
    because: Mapped[str] = mapped_column(String(300))
    reasons_json: Mapped[str] = mapped_column(Text)  # the top SHAP reasons, as JSON
    topics_json: Mapped[str] = mapped_column(Text)  # main topics and keywords found, as JSON
    outside_training_subjects: Mapped[bool] = mapped_column(Boolean)


def get_engine(db_path: Path) -> Engine:
    """Return a SQLAlchemy engine for the SQLite file at db_path."""
    return create_engine(f"sqlite:///{Path(db_path).as_posix()}")


def init_db(engine: Engine) -> None:
    """Create all tables that do not exist yet."""
    Base.metadata.create_all(engine)


def _number(value: str) -> float | None:
    """Return a value as a number, or None if it is empty or not a number."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_records(sources: dict) -> list[Base]:
    """Turn the pipeline's output rows into database records, ready to add in one go.

    sources holds: papers (manifest rows), questions (cleaned rows with question_id),
    topics (owner's naming sheet rows), shares ({question_id: [share per topic]}),
    explanations ({question_id: explanation}), labels ({question_id: label}) and
    departments ({paper_id: department}).
    """
    records: list[Base] = []
    for row in sources["papers"]:
        records.append(Paper(
            id=int(row["paper_id"]), course=row["course"], course_name=row.get("course_name", ""),
            department=sources["departments"][row["paper_id"]], year=int(_number(row["year"]) or 0) or None,
            exam_type=row["exam_type"], semester=row.get("semester", ""), path=row["path"],
            n_pages=int(_number(row.get("n_pages")) or 0) or None,
        ))
    for row in sources["topics"]:
        records.append(Topic(id=int(row["topic"]), name=row["name"].strip() or f"Topic {row['topic']}",
                             keywords=row["keywords"], model=row["model"]))
    for number, row in enumerate(sources["questions"], start=1):
        key = row["question_id"]
        shares = sources["shares"].get(key, [])
        dominant = max(range(len(shares)), key=lambda i: shares[i]) + 1 if any(shares) else None
        records.append(Question(
            id=number, question_key=key, paper_id=int(row["paper_id"]), qno=row["qno"],
            sub_part=row["sub_part"], alternative=int(_number(row["alternative"]) or 0),
            marks=_number(row["marks"]), co=row["co"], text=row["text"], clean_text=row["clean_text"],
            dominant_topic=dominant, owner_label=sources["labels"].get(key),
        ))
        records += [QuestionTopic(question_id=number, topic_id=topic, share=share)
                    for topic, share in enumerate(shares, start=1) if share > 0]
        explanation = sources["explanations"].get(key)
        if explanation:
            p = explanation["probabilities"]
            records.append(Prediction(
                question_id=number, model=explanation.get("model", "random_forest"),
                predicted=explanation["predicted"], p_easy=p["Easy"], p_medium=p["Medium"], p_hard=p["Hard"],
                because=explanation["because"], reasons_json=json.dumps(explanation["reasons"]),
                topics_json=json.dumps(explanation["topics"]),
                outside_training_subjects=bool(explanation["outside_training_subjects"]),
            ))
    return records


def build_database(sources: dict, db_path: Path) -> dict[str, int]:
    """Rebuild the database from scratch and return how many rows each table got.

    Everything is written to <db_path>.tmp, which replaces the old file only at the end.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = db_path.with_suffix(db_path.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    engine = get_engine(temporary)
    init_db(engine)
    records = build_records(sources)
    with Session(engine) as session:
        session.add_all(records)
        session.commit()
    engine.dispose()
    os.replace(temporary, db_path)
    counts: dict[str, int] = {}
    for record in records:
        counts[record.__tablename__] = counts.get(record.__tablename__, 0) + 1
    return counts
