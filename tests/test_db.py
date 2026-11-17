"""The database build. Every paper and question here is fake."""

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from questioniq.db import Paper, Prediction, Question, QuestionTopic, Topic, build_database, get_engine

EXPLANATION = {"predicted": "Hard", "probabilities": {"Easy": 0.1, "Medium": 0.3, "Hard": 0.6},
               "because": "Hard because: fake", "reasons": [{"text": "fake", "shap": 0.1}],
               "topics": {"topics": []}, "outside_training_subjects": False}


def sources() -> dict:
    return {
        "papers": [{"paper_id": "7", "course": "CS1", "course_name": "Fake", "year": "2024",
                    "exam_type": "Endterm", "semester": "V", "path": "fake.pdf", "n_pages": "2"}],
        "departments": {"7": "CS"},
        "questions": [
            {"question_id": "7-1", "paper_id": "7", "qno": "1", "sub_part": "", "alternative": "0",
             "marks": "5", "co": "CO1", "text": "Fake one", "clean_text": "fake"},
            {"question_id": "7-2", "paper_id": "7", "qno": "2", "sub_part": "a", "alternative": "1",
             "marks": "", "co": "", "text": "Fake two", "clean_text": ""},
        ],
        "topics": [{"topic": "1", "name": "Fake trees", "keywords": "tree node", "model": "nmf"},
                   {"topic": "2", "name": "", "keywords": "matrix", "model": "nmf"}],
        "shares": {"7-1": [0.2, 0.8]},
        "explanations": {"7-1": EXPLANATION},
        "labels": {"7-1": "Hard"},
    }


def test_database_holds_every_table(tmp_path) -> None:
    db = tmp_path / "q.db"
    counts = build_database(sources(), db)
    assert counts == {"papers": 1, "topics": 2, "questions": 2, "question_topics": 2, "predictions": 1}
    with Session(get_engine(db)) as session:
        first = session.scalars(select(Question).where(Question.question_key == "7-1")).one()
        assert (first.dominant_topic, first.owner_label, first.marks) == (2, "Hard", 5.0)
        second = session.scalars(select(Question).where(Question.question_key == "7-2")).one()
        assert (second.marks, second.dominant_topic, second.owner_label) == (None, None, None)
        assert session.get(Topic, 2).name == "Topic 2"  # no owner name yet
        assert session.get(Paper, 7).department == "CS"
        prediction = session.scalars(select(Prediction)).one()
        assert prediction.p_hard == 0.6 and json.loads(prediction.reasons_json)[0]["text"] == "fake"


def test_rebuilding_gives_the_same_database_and_leaves_no_temporary_file(tmp_path) -> None:
    db = tmp_path / "q.db"
    build_database(sources(), db)
    build_database(sources(), db)
    with Session(get_engine(db)) as session:
        assert session.scalar(select(func.count()).select_from(Question)) == 2
        assert session.scalar(select(func.count()).select_from(QuestionTopic)) == 2
    assert not (tmp_path / "q.db.tmp").exists()
