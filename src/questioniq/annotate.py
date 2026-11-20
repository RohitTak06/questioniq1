"""The logic behind the owner's difficulty labelling (Phase 4).

Code here never decides a label. It picks which questions to show, stores the
labels the owner clicks, keeps the rounds apart and compares them afterwards.

- Round 1: a fixed sample of questions, spread across departments, in shuffled order.
- Round 2: a fixed sample of round-1 questions, opened only when round 1 is complete
  and 48 hours have passed since its last label, so the owner can't remember answers.
- Agreement between the rounds is Cohen's Kappa.
"""

import csv
import hashlib
import io
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sklearn.metrics import cohen_kappa_score, confusion_matrix

ANNOTATORS = ("round1", "round2", "helper")
GRADES = ["Easy", "Medium", "Hard"]  # Skip is a choice on the page, but not a grade
QUEUE_COLUMNS = ["question_id", "paper_id", "course", "text_hash"]
LABEL_COLUMNS = ["question_id", "label", "labelled_at"]

MARK_NUMBER = r"\d{1,2}(?:\.\d)?(?:\s*[+x×*]\s*\d{1,2}(?:\.\d)?)*"
MARKS_IN_TEXT = re.compile(
    rf"\[\s*{MARK_NUMBER}\s*(?:marks?|m)?\s*\]"  # [5], [2+3]
    rf"|\(\s*{MARK_NUMBER}\s*marks?\s*\)"  # (5 marks)
    rf"|\b{MARK_NUMBER}\s*marks?\b"  # 5 marks, 2+3 Marks
    r"|\bmarks?\b",  # a leftover "Marks" column header
    re.I,
)


def text_hash(text: str) -> str:
    """Return a short fingerprint of a question's text, to notice if the data changes."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def add_question_ids(rows: list[dict]) -> list[dict]:
    """Give each question an ID: its paper and its position in that paper, such as 33-4."""
    counters: dict[str, int] = {}
    with_ids = []
    for row in rows:
        counters[row["paper_id"]] = counters.get(row["paper_id"], 0) + 1
        with_ids.append({**row, "question_id": f"{row['paper_id']}-{counters[row['paper_id']]}"})
    return with_ids


def id_order(question_id: str) -> tuple[int, int]:
    """Return a sort key that puts 33-2 before 33-10 and 9-1 before 33-1."""
    paper, position = question_id.split("-")
    return int(paper), int(position)


def department(course: str) -> str:
    """Return the two department letters of a course code: CS1140 -> CS.

    Only two letters are kept because CSE1132 and CSE1135 are older codes for the CS
    courses CS1132 and CS1135; every other department code has two letters.
    """
    match = re.match(r"[A-Za-z]+", course)
    return match.group(0)[:2].upper() if match else course


def labelling_pool(
    rows: list[dict], min_words: int, max_words: int, departments: list[str] | None = None
) -> list[dict]:
    """Return the questions fit to label: some words left after cleaning, a sane length,
    and (if departments are given) from a department the owner has studied.

    Very short and very long rows are mostly segmentation errors.
    """
    wanted = {name.upper() for name in departments} if departments else None
    return [
        row
        for row in rows
        if int(row["n_tokens"]) > 0
        and min_words <= len(row["text"].split()) <= max_words
        and (wanted is None or department(row["course"]) in wanted)
    ]


def proportional_shares(sizes: dict[str, int], n: int) -> dict[str, int]:
    """Share n picks across groups in proportion to their size, at least one per group.

    Uses the largest-remainder method: everyone gets the whole part of their share,
    and the picks left over go to the groups with the biggest fractions.
    """
    total = sum(sizes.values())
    n = min(n, total)
    exact = {group: n * size / total for group, size in sizes.items()}
    shares = {group: min(size, max(1, int(exact[group]))) for group, size in sizes.items()}
    by_remainder = sorted(sizes, key=lambda group: (-(exact[group] % 1), group))
    while sum(shares.values()) < n:
        for group in by_remainder:
            if sum(shares.values()) < n and shares[group] < sizes[group]:
                shares[group] += 1
    while sum(shares.values()) > n:
        biggest = max(shares, key=lambda group: (shares[group], group))
        shares[biggest] -= 1
    return shares


def queue_row(row: dict) -> dict:
    """Return the queue entry for a question: no exam text, only its ID and fingerprint."""
    return {
        "question_id": row["question_id"],
        "paper_id": row["paper_id"],
        "course": row["course"],
        "text_hash": text_hash(row["text"]),
    }


def draw_round1(pool: list[dict], n: int, rng: random.Random) -> list[dict]:
    """Draw n questions spread across departments, then shuffle them into one queue."""
    by_department: dict[str, list[dict]] = {}
    for row in pool:
        by_department.setdefault(department(row["course"]), []).append(row)
    shares = proportional_shares({name: len(rows) for name, rows in by_department.items()}, n)
    picked = []
    for name in sorted(shares):
        candidates = sorted(by_department[name], key=lambda row: id_order(row["question_id"]))
        picked += rng.sample(candidates, shares[name])
    rng.shuffle(picked)
    return [queue_row(row) for row in picked]


def draw_round2(queue1: list[dict], labels1: dict[str, str], n: int, rng: random.Random) -> list[dict]:
    """Draw n round-1 questions that got a grade (not Skip), in a new random order."""
    graded = [row for row in queue1 if labels1.get(row["question_id"]) in GRADES]
    graded.sort(key=lambda row: id_order(row["question_id"]))
    return rng.sample(graded, min(n, len(graded)))


def read_rows(path: Path) -> list[dict]:
    """Return the rows of a CSV file, or an empty list if it doesn't exist yet.

    Excel on Windows saves CSV files in the Windows-1252 character set, not UTF-8, so that
    is tried when the file isn't valid UTF-8.
    """
    if not path.exists():
        return []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def write_rows(path: Path, rows: list[dict], columns: list[str]) -> None:
    """Write rows to a CSV file, creating its folder if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def now_utc() -> datetime:
    """Return the current time in UTC, to the second."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def append_label(path: Path, question_id: str, label: str, when: datetime) -> None:
    """Add one label to an annotator's file. Old rows are kept, so changes have a history."""
    new_file = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow({"question_id": question_id, "label": label, "labelled_at": when.isoformat()})


def latest_labels(rows: list[dict]) -> dict[str, str]:
    """Return each question's most recent label. A later click replaces an earlier one."""
    return {row["question_id"]: row["label"] for row in rows}


def first_unlabelled(queue: list[dict], labels: dict[str, str]) -> int:
    """Return the position of the first question without a label, or len(queue) if none."""
    for index, row in enumerate(queue):
        if row["question_id"] not in labels:
            return index
    return len(queue)


def round2_opens_at(queue1: list[dict], label_rows1: list[dict], delay_hours: float) -> datetime | None:
    """Return when round 2 may start, or None while round 1 is still incomplete."""
    labels = latest_labels(label_rows1)
    if not queue1 or first_unlabelled(queue1, labels) < len(queue1):
        return None
    last = max(datetime.fromisoformat(row["labelled_at"]) for row in label_rows1)
    return last + timedelta(hours=delay_hours)


def queue_problems(queue: list[dict], questions: dict[str, dict]) -> list[str]:
    """Return queue IDs whose question is missing or whose text changed since the draw."""
    return [
        row["question_id"]
        for row in queue
        if row["question_id"] not in questions
        or text_hash(questions[row["question_id"]]["text"]) != row["text_hash"]
    ]


def hide_marks(text: str) -> str:
    """Remove marks written inside a question's text ([5], (5 marks), 2+3 Marks).

    Bare numbers are left alone, since they can't be told apart from numbers in the
    question itself, so a few marks may still show.
    """
    return " ".join(MARKS_IN_TEXT.sub(" ", text).split())


def agreement_report(labels_a: dict[str, str], labels_b: dict[str, str]) -> dict:
    """Compare two sets of labels on the questions both graded (Skips left out).

    Returns Cohen's Kappa, the share of identical labels, the confusion matrix
    (rows: first set, columns: second set, in the order Easy, Medium, Hard) and the
    questions where they differ.
    """
    common = sorted(
        (qid for qid in labels_a if labels_a[qid] in GRADES and labels_b.get(qid) in GRADES),
        key=id_order,
    )
    a = [labels_a[qid] for qid in common]
    b = [labels_b[qid] for qid in common]
    kappa = float(cohen_kappa_score(a, b, labels=GRADES)) if len(set(a) | set(b)) > 1 else None
    return {
        "n_compared": len(common),
        "kappa": kappa,
        "agreement": sum(x == y for x, y in zip(a, b)) / len(common) if common else None,
        "labels": GRADES,
        "confusion_matrix": confusion_matrix(a, b, labels=GRADES).tolist() if common else None,
        "disagreements": [
            {"question_id": qid, "first": labels_a[qid], "second": labels_b[qid]}
            for qid in common
            if labels_a[qid] != labels_b[qid]
        ],
    }
