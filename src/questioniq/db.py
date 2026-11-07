"""SQLite database models; their columns are added in Phase 7."""

from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database tables."""


class Paper(Base):
    """One downloaded or uploaded exam paper."""

    __tablename__ = "papers"
    id: Mapped[int] = mapped_column(primary_key=True)


class Question(Base):
    """One question extracted from a paper."""

    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(primary_key=True)


class Topic(Base):
    """One discovered topic with its owner-given name."""

    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)


class Prediction(Base):
    """One difficulty prediction for a question."""

    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)


def get_engine(db_path: Path) -> Engine:
    """Return a SQLAlchemy engine for the SQLite file at db_path."""
    raise NotImplementedError


def init_db(engine: Engine) -> None:
    """Create all tables that do not exist yet."""
    raise NotImplementedError
