"""Pages of the app. Phase 4: the labelling page; Phase 8 adds the dashboard."""

import random
from pathlib import Path

from flask import Blueprint, abort, current_app, redirect, render_template, request, send_file, url_for
from flask.typing import ResponseReturnValue

from questioniq.annotate import (
    ANNOTATORS,
    QUEUE_COLUMNS,
    add_question_ids,
    append_label,
    draw_round2,
    first_unlabelled,
    hide_marks,
    latest_labels,
    now_utc,
    queue_problems,
    read_rows,
    round2_opens_at,
    write_rows,
)
from questioniq.scrape import read_manifest

bp = Blueprint("main", __name__)


def _cfg() -> dict:
    """Return the project config the app was built with."""
    return current_app.config["QIQ"]


def _labels_path(annotator: str) -> Path:
    """Return an annotator's label file: data/labels/difficulty_<annotator>.csv."""
    return Path(_cfg()["paths"]["labels"]) / f"difficulty_{annotator}.csv"


def _questions() -> dict[str, dict]:
    """Return all cleaned questions by their ID."""
    rows = add_question_ids(read_rows(Path(_cfg()["paths"]["questions_clean"])))
    return {row["question_id"]: row for row in rows}


def _rubric() -> str | None:
    """Return the owner's rubric text, or None if it hasn't been written yet."""
    path = Path(_cfg()["paths"]["rubric"])
    text = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    return text or None


def _message(title: str, body: str, status: int = 200) -> ResponseReturnValue:
    """Show a page with a message instead of a question."""
    return render_template("message.html", title=title, body=body), status


def _queue(annotator: str) -> tuple[list[dict] | None, str | None]:
    """Return an annotator's queue, or None and the reason it can't open yet.

    Round 1 and the helper share the round-1 queue. Round 2's queue is drawn once,
    the first time it opens, and saved so it never changes after that.
    """
    paths = _cfg()["paths"]
    settings = _cfg()["annotation"]
    queue1 = read_rows(Path(paths["round1_queue"]))
    if not queue1:
        return None, "The round-1 queue hasn't been drawn yet. Run scripts/make_label_queue.py."
    round2_path = Path(paths["round2_queue"])
    if annotator in ("round1", "helper"):
        if annotator == "round1" and round2_path.exists():
            return None, "Round 1 is closed because round 2 has started, so the rounds stay independent."
        return queue1, None
    if round2_path.exists():
        return read_rows(round2_path), None
    label_rows1 = read_rows(_labels_path("round1"))
    opens_at = round2_opens_at(queue1, label_rows1, settings["relabel_delay_hours"])
    if opens_at is None:
        done = len(latest_labels(label_rows1).keys() & {row["question_id"] for row in queue1})
        return None, f"Round 1 isn't finished yet: {done} of {len(queue1)} questions labelled."
    if now_utc() < opens_at:
        return None, f"Round 2 opens at {opens_at.astimezone().strftime('%d %b %Y, %H:%M')}."
    rng = random.Random(_cfg()["random_state"])
    queue2 = draw_round2(queue1, latest_labels(label_rows1), settings["relabel_n"], rng)
    write_rows(round2_path, queue2, QUEUE_COLUMNS)
    return queue2, None


def _open(annotator: str) -> tuple[tuple[list[dict], dict[str, dict]] | None, ResponseReturnValue | None]:
    """Return (queue, questions) for an annotator, or a message page explaining why not."""
    if annotator not in ANNOTATORS:
        abort(400, f"annotator must be one of {', '.join(ANNOTATORS)}")
    if _rubric() is None:
        return None, _message(
            "Write the rubric first",
            "Labelling opens once docs/rubric.md describes what makes a question Easy, Medium "
            "or Hard, so every label follows written rules.",
        )
    queue, reason = _queue(annotator)
    if queue is None:
        return None, _message("Not open", reason)
    questions = _questions()
    problems = queue_problems(queue, questions)
    if problems:
        return None, _message(
            "The questions changed",
            "These queued questions are missing or their text changed since the queue was "
            f"drawn, so labels could land on the wrong question: {', '.join(problems[:20])}",
            status=409,
        )
    return (queue, questions), None


@bp.get("/")
def index() -> ResponseReturnValue:
    """Show links to the labelling rounds."""
    return render_template("index.html", annotators=ANNOTATORS)


@bp.get("/paper/<paper_id>.pdf")
def paper_pdf(paper_id: str) -> ResponseReturnValue:
    """Open a paper's original PDF, so a question garbled by OCR can be read from the scan.

    Only papers listed in the manifest are served, and only from this computer's data/raw.
    """
    row = read_manifest(Path(_cfg()["paths"]["manifest"])).get(paper_id)
    if row is None or not Path(row["path"]).is_file():
        abort(404, "paper not found")
    return send_file(Path(row["path"]).resolve(), mimetype="application/pdf")


@bp.get("/annotate")
def annotate() -> ResponseReturnValue:
    """Show one question to label, with this annotator's own label if it has one."""
    annotator = request.args.get("annotator", "")
    opened, message = _open(annotator)
    if message is not None:
        return message
    queue, questions = opened
    labels = latest_labels(read_rows(_labels_path(annotator)))
    index = request.args.get("i", type=int)
    if index is None:
        index = first_unlabelled(queue, labels)
    if index >= len(queue):
        done = sum(row["question_id"] in labels for row in queue)
        return _message("All done", f"{done} of {len(queue)} questions labelled in {annotator}.")
    index = max(index, 0)
    question = questions[queue[index]["question_id"]]
    text = question["text"] if _cfg()["annotation"]["show_marks"] else hide_marks(question["text"])
    return render_template(
        "annotate.html",
        annotator=annotator,
        index=index,
        total=len(queue),
        done=sum(row["question_id"] in labels for row in queue),
        question=question,
        text=text,
        current=labels.get(question["question_id"]),
        choices=_cfg()["annotation"]["choices"],
        rubric=_rubric(),
    )


@bp.post("/annotate")
def save_label() -> ResponseReturnValue:
    """Save one label the owner clicked, then show the next question."""
    annotator = request.form.get("annotator", "")
    opened, message = _open(annotator)
    if message is not None:
        return message
    queue, _ = opened
    question_id = request.form.get("question_id", "")
    label = request.form.get("label", "")
    queued = [row["question_id"] for row in queue]
    if question_id not in queued or label not in _cfg()["annotation"]["choices"]:
        abort(400, "unknown question or label")
    append_label(_labels_path(annotator), question_id, label, now_utc())
    return redirect(url_for("main.annotate", annotator=annotator, i=queued.index(question_id) + 1))
