"""Split a paper's text into individual questions (Phase 1).

A paper's text has one line per OCR line. Marks and CO cells found at the far
right of the page follow a tab, so a line reads "body<TAB>right".

One row per question, except: sub-parts become separate rows only when each has
its own marks, and each OR option is its own row. Everything here only reads the
text. Odd results are flagged by check_paper, never silently corrected.
"""

import re
from dataclasses import dataclass, field

# Groups: number, second-level number (Q.1.2), part letter (Q2A), rest of the line.
# One stray lowercase letter before the Q is OCR noise from a table rule (gQ.6).
Q_START = re.compile(
    r"^\W*[a-z]?(?:Q(?:ues)?|[Qq]uestion|QUESTION)[\W_]{0,3}(?:No\W{0,2})?"
    r"([0-9Il][0-9IlO]?)(?:\s?\.(\d)(?!\d))?([A-Ha-h]?)(?![A-Za-z0-9])\W*(.*)$"
)
# A Q read as 0 or O: (O4 Design, 0.8 Definition, 0.3.1 Discuss.
Q_MISREAD = re.compile(r"^\W*[O0][\W_]{0,2}(\d{1,2})(?:\.(\d)(?!\d))?\b\W*([A-Za-z(].*)$")
# A Q whose number was read as a letter: Q.g Let, (Qi A State, QiB Fill. Groups: letter, part, rest.
Q_LETTER = re.compile(r"^\W*Q[\W_]{0,2}([A-Za-z])([A-Ha-h]?)(?![A-Za-z0-9])\W*([A-Z].*)$")
NUMBER_START = re.compile(r"^\W*\(?(\d{1,2})\s*[.),]\s+(\S.*)$")  # 4, is a misread 4.
NUMBER_LETTER_START = re.compile(r"^\W*(\d{1,2})\s*\(([a-hA-H])\)\W*\s*(\S.*)$")  # 1(a). Provide
NUMBER_BARE_LETTER = re.compile(r"^\W*(\d{1,2})[.)]?\s+([a-h][.)]?\s+\S.*)$")  # 2 a Explain
BARE_START = re.compile(r"^\W*(\d{1,2})\W*\s+([A-Z(].*)$")
TABLE_HEADER = re.compile(r"\b(?:sr|s)\W{0,2}no\b|\bquestions?\b.*\bmarks\b", re.I)
LETTER_PART = re.compile(r"^\W*\(?([a-hA-H])(?:[).]\s+|\s+(?=[A-Z]))(\S.*)$")  # a) x, B. X, b Write
ROMAN_PART = re.compile(r"^\W*\(?(i{1,3}|iv|vi{0,3}|ix|x)[).]\s+(\S.*)$")
NUMBER_PART = NUMBER_START
OR_LINE = re.compile(r"^\W*(?:OR|Or)\W*$")
NOISE_LINE = re.compile(
    r"^\W*(?:page\W*\w{0,3}\W*of(?:\W*\d+){0,2}|roll\W*n\w*\b.*|best of luck.*|all the best.*"
    r"|(?:section|part)\W*[A-C0-9I]{1,3}\W*|\W*)$",
    re.I,
)
INSTRUCTION = re.compile(
    r"do not write|\broll n|\binstructions?\b|\b(?:attempt|answer) (?:any|all)\b"
    r"|all questions (?:are|carry)|\bcompulsory\b|\bcalculators?\b|assume suitable"
    r"|figures? (?:to|in) the right|question paper|mobile phone",
    re.I,
)
INSTRUCTIONS_HEADER = re.compile(r"\binstructions?\b", re.I)
ATTEMPT_ANY = re.compile(r"\b(?:attempt|answer) any\b", re.I)
EQUAL_MARKS = re.compile(r"\bequal marks\b", re.I)
PASSAGE_START = re.compile(r"case\s*(?:study|let)|\bpassage\b|\bbackground\b", re.I)
MARKS_IN_BODY = re.compile(
    r"[\[(]\s*(\d{1,2}(?:\.\d)?)\s*(?:marks?|m)?\s*[\])]?\s*$"  # [5], (5 marks), [5
    r"|\b(\d{1,2}(?:\.\d)?)\s*(?:marks?\b|M\b)\W*$",  # 5 marks, 5M
    re.I,
)
MARKS_PRODUCT = re.compile(r"\b(\d{1,2})\s*[xX×*]\s*(\d{1,2})\W*$")  # 4x3
MARKS_SUM = re.compile(r"\b(\d{1,2}(?:\s*\+\s*\d{1,2})+)\W*$")  # 2+4
MARKS_IN_CELL = re.compile(r"(?<![\w.])[\[(]?(\d{1,2}(?:\.\d)?)[\])]?(?![\w.])")
CO_LABEL = re.compile(r"\b([CLI])[O0]\s*-?\s*([\dlI](?:\s*,\s*[\dlI])*)")
TRAILING_LABEL = re.compile(r"[\s(]*\b[CLI][O0]\s*-?\s*[\dlI][\dlI,\s]*\)?\W*$")
MAX_MARKS = re.compile(r"max(?:imum)?\W*marks?\W*(\d{1,3})", re.I)
NOISE_CHARS = re.compile(r"^[\s|_~—–=]+|[\s|_~—–=]+$")


@dataclass
class Question:
    """One question or sub-part, with its marks and course outcome if found.

    alternative is 0 for ordinary questions, and 1, 2, ... for OR options.
    """

    qno: str
    sub_part: str | None
    text: str
    marks: float | None
    co: str | None
    alternative: int = 0


@dataclass
class _Block:
    """The lines from one question start up to the next."""

    qno: str
    sub_part: str | None
    lines: list[tuple[str, str]] = field(default_factory=list)
    position: tuple[int, int] | None = None  # (number, second-level number) used for ordering


def normalise_qno(raw: str) -> str:
    """Undo common OCR misreads inside a question number: I and l for 1, O for 0."""
    return raw.replace("I", "1").replace("l", "1").replace("O", "0")


def split_cells(line: str) -> tuple[str, str]:
    """Split a line into its body and right-hand cell, removing table-rule characters."""
    body, _, right = line.partition("\t")
    body = re.sub(r"\s*\|\s*", " ", body)
    return NOISE_CHARS.sub("", body), right.strip()


def is_noise_line(body: str) -> bool:
    """Return True for page markers, roll-number lines and section headings."""
    return bool(NOISE_LINE.match(body))


def is_instruction(line: str) -> bool:
    """Return True for headers and instructions, which are not questions."""
    return len(line.split()) <= 30 and bool(INSTRUCTION.search(line))


def body_marks(body: str) -> float | None:
    """Return marks written at the end of a line: [5], (5 marks), 5M, 4x3 or 2+4, or None."""
    text = TRAILING_LABEL.sub("", body)
    product = MARKS_PRODUCT.search(text)
    if product:
        return float(product.group(1)) * float(product.group(2))
    total = MARKS_SUM.search(text)
    if total:
        return float(sum(int(part) for part in total.group(1).split("+")))
    match = MARKS_IN_BODY.search(text)
    return float(match.group(1) or match.group(2)) if match else None


def parse_marks(cell: str) -> float | None:
    """Return the marks in a right-hand cell or at the end of a line, or None."""
    if not cell.strip():
        return None
    marks = body_marks(cell)
    if marks is not None:
        return marks
    without_labels = CO_LABEL.sub(" ", TRAILING_LABEL.sub("", cell))  # (LO1 3) is a label
    if re.fullmatch(r"[\s\d.,\[\]()]*", without_labels):
        found = MARKS_IN_CELL.search(without_labels)
        if found:
            return float(found.group(1))
    return None


def parse_co(cell: str) -> str | None:
    """Return course-outcome labels such as CO1,2 or LO3, undoing common OCR misreads."""
    labels = []
    for kind, numbers in CO_LABEL.findall(cell):
        digits = normalise_qno(re.sub(r"\s", "", numbers))
        labels.append(f"{'C' if kind == 'C' else 'L'}O{digits}")
    return ",".join(labels) or None


def paper_style(bodies: list[str]) -> str:
    """Return how a paper numbers its questions: "q", "table", "number" or "none"."""
    usable = [body for body in bodies if not is_instruction(body)]
    q_starts = sum(bool(Q_START.match(body)) for body in usable)
    if q_starts >= 2:
        return "q"
    if any(TABLE_HEADER.search(body) for body in bodies):
        return "table"
    if any(NUMBER_START.match(body) or NUMBER_LETTER_START.match(body) for body in usable):
        return "number"
    return "q" if q_starts else "none"


def _number_match(body: str) -> tuple[int, str | None, str] | None:
    """Return (number, letter, rest) if a line starts with a plain question number."""
    paired = NUMBER_LETTER_START.match(body)
    if paired:
        return int(paired.group(1)), paired.group(2), paired.group(3)
    match = NUMBER_START.match(body) or NUMBER_BARE_LETTER.match(body) or BARE_START.match(body)
    return (int(match.group(1)), None, match.group(2)) if match else None


def _explicit_number(body: str) -> int | None:
    """Return the number of a line with a clear Q label (Q3, Q.3.1), or None."""
    match = Q_START.match(body)
    if not match or is_instruction(body):
        return None
    number = normalise_qno(match.group(1))
    return int(number) if number.isdigit() else None


def _next_explicit(bodies: list[str]) -> list[int | None]:
    """For each line, return the number of the next clearly labelled question after it."""
    upcoming: list[int | None] = [None] * len(bodies)
    following = None
    for index in range(len(bodies) - 1, -1, -1):
        upcoming[index] = following
        number = _explicit_number(bodies[index])
        if number is not None:
            following = number
    return upcoming


def _q_style_start(
    body: str, last: tuple[int, int], in_numbered_steps: bool, upcoming: int | None
) -> tuple[_Block, str] | None:
    """Return a new block for a line in a Q1-style paper, or None.

    last is the (number, second-level number) of the previous question. A clear Q label
    always counts. A guessed start counts only if it is the next number expected and the
    next clear Q label after it has a bigger number:
    - a Q misread as 0 or O (O4, 0.3.1), kept as written;
    - a Q whose number was read as a letter (Q.g, Qi), kept as that letter and flagged;
    - a lost Q (a bare 4), but not once the question has started its own 1, 2, 3 steps.
    """
    if is_instruction(body):
        return None
    match = Q_START.match(body)
    if match:
        number = normalise_qno(match.group(1))
        second = match.group(2)
        block = _Block(number, second or match.group(3) or None)
        if number.isdigit():
            block.position = (int(number), int(second or 0))
        return block, match.group(4)
    number, second = last
    lettered = Q_LETTER.match(body)
    if lettered and (upcoming is None or upcoming > number + 1):
        block = _Block(lettered.group(1), lettered.group(2) or None, position=(number + 1, 0))
        return block, lettered.group(3)
    if not number:
        return None
    misread = Q_MISREAD.match(body)
    if misread:
        found_number = int(misread.group(1))
        found_second = int(misread.group(2) or 0)
        next_number = found_number == number + 1
        next_second = found_second and found_number == number and found_second > second
        allowed = upcoming is None or upcoming > found_number or (found_second and upcoming == found_number)
        if (next_number or next_second) and allowed:
            block = _Block(misread.group(1), misread.group(2), position=(found_number, found_second))
            return block, misread.group(3)
    found = _number_match(body)
    if (
        found
        and found[0] == number + 1
        and not in_numbered_steps
        and (upcoming is None or upcoming > found[0])
    ):
        return _Block(str(found[0]), found[1], position=(found[0], 0)), found[2]
    return None


def _numbered_line_above(previous: list[tuple[str, str]], block: _Block) -> tuple[str, str] | None:
    """Return the line above a Q label if it starts with the same bare number, minus that number.

    When the number sits between two lines, OCR can give "2 First line" then "Q2. second
    line". The first line belongs to Q2, not to the question before it. Not when the
    question before has its own 1, 2, 3 steps, since its step 2 can sit just above Q2.
    """
    if len(previous) < 2 or not block.qno.isdigit() or block.position is None:
        return None
    if _has_numbered_steps(_Block("", None, previous[:-1])):
        return None
    body, right = previous[-1]
    found = _number_match(body)
    if found and found[0] == int(block.qno) and found[1] is None:
        return found[2], right
    return None


def _takes_marks_line(
    previous: list[tuple[str, str]], earlier_has_marks: bool, start_right: str
) -> bool:
    """Return True if the line just before a question start belongs to that question.

    In table layouts the question number sits in the middle of a tall cell, so the
    question's first line (with its marks) comes out just above the number. That line is
    moved only if it carries marks, the question before it already had marks, and the
    start line has no marks of its own. A labelled part (a, i, 1), an OR line or the
    first line after an OR stays where it is.
    """
    if not previous or parse_marks(start_right) is not None:
        return False
    body, right = previous[-1]
    if parse_marks(right) is None or not earlier_has_marks:
        return False
    if len(previous) >= 2 and OR_LINE.match(previous[-2][0]):
        return False
    if OR_LINE.match(body) or is_instruction(body) or re.search(r"marks", body, re.I):
        return False
    return not any(pattern.match(body) for pattern in (LETTER_PART, ROMAN_PART, NUMBER_PART))


def _has_numbered_steps(block: _Block | None) -> bool:
    """Return True if a question has started its own steps with a line numbered 1."""
    if block is None:
        return False
    return any((match := NUMBER_START.match(body)) and match.group(1) == "1" for body, _ in block.lines)


def _find_blocks(lines: list[tuple[str, str]], style: str) -> tuple[list[str], list[_Block]]:
    """Group lines into question blocks. Lines before the first question are returned apart."""
    before_lines: list[tuple[str, str]] = []
    blocks: list[_Block] = []
    last = 0
    q_last = (0, 0)
    restarted = False
    upcoming = _next_explicit([body for body, _ in lines]) if style == "q" else []
    for index, (body, right) in enumerate(lines):
        before = [line[0] for line in before_lines]
        new_block = None
        rest = body
        if style == "q":
            current = blocks[-1] if blocks else None
            start = _q_style_start(body, q_last, _has_numbered_steps(current), upcoming[index])
            if start:
                new_block, rest = start
                position = new_block.position
                # A clear label far beyond the next number is likely misread (Q35 for Q5):
                # it is kept as written, but doesn't move the expected next number.
                if position and (not q_last[0] or position[0] <= q_last[0] + 3):
                    q_last = position
        else:
            found = _number_match(body)
            if found and not is_instruction(found[2]):
                number, letter, candidate = found
                after_header = any(INSTRUCTIONS_HEADER.search(line) for line in before)
                if (
                    number == 1
                    and blocks
                    and after_header
                    and not restarted
                    and not letter
                    and not any(_block_has_marks(block) for block in blocks)
                ):
                    # A second "1." after an instructions header means the first run was instructions.
                    before_lines += [line for block in blocks for line in block.lines]
                    blocks, last, restarted = [], 0, True
                repeats = letter is not None and number == last
                if (last == 0 and number <= 3) or last < number <= last + 3 or repeats:
                    new_block = _Block(str(number), letter)
                    rest = candidate
                    last = number
        if new_block is not None:
            if blocks:
                previous = blocks[-1].lines
                earlier = len(previous) >= 2 and _lines_marks(previous[:-1]) is not None
            else:
                previous, earlier = before_lines, True
            numbered = _numbered_line_above(previous, new_block)
            if numbered is not None:
                previous.pop()
                new_block.lines.append(numbered)
            elif _takes_marks_line(previous, earlier, right):
                new_block.lines.append(previous.pop())
            blocks.append(new_block)
            blocks[-1].lines.append((rest, right))
        elif blocks:
            blocks[-1].lines.append((body, right))
        else:
            before_lines.append((body, right))
    return [line[0] for line in before_lines], blocks


def _block_has_marks(block: _Block) -> bool:
    """Return True if any line of a block carries marks."""
    return _lines_marks(block.lines) is not None


def _lines_marks(lines: list[tuple[str, str]]) -> float | None:
    """Return the first marks found in some lines, preferring the right-hand cell."""
    for body, right in lines:
        marks = parse_marks(right)
        if marks is None:
            marks = body_marks(body)
        if marks is not None:
            return marks
    return None


def _lines_co(lines: list[tuple[str, str]]) -> str | None:
    """Return the course-outcome labels in the right-hand cells or at the ends of some lines."""
    labels = []
    for body, right in lines:
        trailing = TRAILING_LABEL.search(body)
        label = parse_co(right) or (parse_co(body[trailing.start() :]) if trailing else None)
        if label:
            labels.append(label)
    return ",".join(dict.fromkeys(labels)) or None


def _lines_text(lines: list[tuple[str, str]]) -> str:
    """Join line bodies into one text, leaving out instructions and empty lines."""
    return " ".join(body for body, _ in lines if body and not is_instruction(body))


def _split_or(lines: list[tuple[str, str]]) -> tuple[list[list[tuple[str, str]]], bool]:
    """Split lines at OR lines. Also say whether an OR ends the block."""
    options: list[list[tuple[str, str]]] = [[]]
    for line in lines:
        if OR_LINE.match(line[0]):
            options.append([])
        else:
            options[-1].append(line)
    trailing_or = len(options) > 1 and not options[-1]
    return [option for option in options if option], trailing_or


def _split_parts(
    lines: list[tuple[str, str]], allow_numeric: bool
) -> tuple[list[tuple[str, str]], list[tuple[str, list[tuple[str, str]]]]]:
    """Split lines into a shared stem and labelled sub-parts: a, b, c or i, ii, iii or 1, 2, 3.

    A label only counts if it is the next one expected, so a stray "a." is left in the text.
    """
    sequences = {
        "letter": (LETTER_PART, list("abcdefgh")),
        "roman": (ROMAN_PART, ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"]),
    }
    if allow_numeric:
        sequences["number"] = (NUMBER_PART, [str(n) for n in range(1, 21)])
    stem: list[tuple[str, str]] = []
    parts: list[tuple[str, list[tuple[str, str]]]] = []
    kind = None
    for body, right in lines:
        matched = None
        for name, (pattern, labels) in sequences.items():
            if kind not in (None, name):
                continue
            match = pattern.match(body)
            expected = labels[len(parts)] if len(parts) < len(labels) else None
            if match and match.group(1).lower() == expected:
                matched = (name, match.group(1), match.group(2))
                break
        if matched:
            kind = matched[0]
            parts.append((matched[1], [(matched[2], right)]))
        elif parts:
            parts[-1][1].append((body, right))
        else:
            stem.append((body, right))
    return stem, parts


def _option_rows(
    block: _Block, lines: list[tuple[str, str]], alternative: int, allow_numeric: bool
) -> list[Question]:
    """Turn one question (or one OR option) into rows, splitting only marked sub-parts."""
    stem, parts = _split_parts(lines, allow_numeric)
    part_marks = [_lines_marks(part_lines) for _, part_lines in parts]
    if len(parts) >= 2 and all(marks is not None for marks in part_marks):
        stem_text = _lines_text(stem)
        return [
            Question(
                block.qno,
                label,
                f"{stem_text} {_lines_text(part_lines)}".strip(),
                marks,
                _lines_co(part_lines) or _lines_co(stem),
                alternative,
            )
            for (label, part_lines), marks in zip(parts, part_marks)
        ]
    known = [marks for marks in part_marks if marks is not None]
    marks = _lines_marks(stem)
    if marks is None and known:
        marks = sum(known)
    if marks is None:
        marks = _lines_marks(lines)
    return [
        Question(
            block.qno, block.sub_part, _lines_text(lines), marks, _lines_co(lines), alternative
        )
    ]


def leading_passage(before: list[str]) -> str:
    """Return a case-study passage from the lines before the first question, if there is one."""
    for index, line in enumerate(before):
        if PASSAGE_START.search(line) and not is_instruction(line):
            return " ".join(before[index:])
    return ""


def segment(text: str) -> list[Question]:
    """Split paper text into questions using numbering rules."""
    lines = [split_cells(line) for line in text.splitlines()]
    # A noise line is kept only if its right cell holds something that isn't noise too
    # ("Page of<TAB>1 3" is a page footer, but "<TAB>5" alone is a marks cell).
    lines = [
        line
        for line in lines
        if not is_noise_line(line[0]) or (line[1] and not is_noise_line(f"{line[0]} {line[1]}"))
    ]
    style = paper_style([body for body, _ in lines])
    if style == "none":
        return []
    before, blocks = _find_blocks(lines, style)
    questions: list[Question] = []
    or_pending = False
    previous_option = 0
    for block in blocks:
        options, trailing_or = _split_or(block.lines)
        if or_pending:
            first = previous_option + 1
        else:
            first = 1 if len(options) > 1 or trailing_or else 0
        for offset, option in enumerate(options):
            alternative = first + offset if first else 0
            questions += _option_rows(block, option, alternative, style == "q")
        or_pending = trailing_or
        previous_option = first + len(options) - 1 if first else 0
    passage = leading_passage(before)
    if passage and questions:
        questions[0].text = f"{passage} {questions[0].text}".strip()
    return questions


def marks_total(questions: list[Question]) -> tuple[float, int]:
    """Return the marks a student can score and how many rows have no marks.

    Only the largest option of an OR group counts, since a student answers one.
    """
    total = 0.0
    missing = sum(question.marks is None for question in questions)
    options: dict[int, float] = {}
    group_qno = None
    for question in questions:
        marks = question.marks or 0.0
        if question.alternative == 0:
            total += max(options.values(), default=0.0) + marks
            options, group_qno = {}, None
            continue
        starts_new = question.alternative == 1 and (1 not in options or question.qno != group_qno)
        if starts_new:
            total += max(options.values(), default=0.0)
            options, group_qno = {}, question.qno
        options[question.alternative] = options.get(question.alternative, 0.0) + marks
    return total + max(options.values(), default=0.0), missing


def find_max_marks(text: str) -> float | None:
    """Return the paper's maximum marks from its header, or None if not found."""
    match = MAX_MARKS.search(text)
    return float(match.group(1)) if match else None


def number_jumps(questions: list[Question]) -> list[str]:
    """Return places where question numbers don't go up by one, such as "7->9"."""
    numbers = [int(q.qno) for q in questions if q.qno.isdigit()]
    unique = list(dict.fromkeys(numbers))
    return [f"{a}->{b}" for a, b in zip(unique, unique[1:]) if b != a + 1]


def check_paper(
    questions: list[Question], text: str, mean_conf: float | None, low_confidence: float
) -> dict:
    """Run the per-paper checks and return the counts and flags. Nothing is corrected."""
    total, missing = marks_total(questions)
    max_marks = find_max_marks(text)
    attempt_any = bool(ATTEMPT_ANY.search(text))
    jumps = number_jumps(questions)
    flags = []
    if not questions:
        flags.append("no_questions")
    if missing:
        flags.append("equal_marks" if EQUAL_MARKS.search(text) else "missing_marks")
    if max_marks is None:
        flags.append("no_max_marks")
    elif questions and not missing and not attempt_any and total != max_marks:
        flags.append("marks_mismatch")
    if attempt_any:
        flags.append("attempt_any")
    if jumps:
        flags.append("number_jump")
    if any(not question.qno.isdigit() for question in questions):
        flags.append("unreadable_qno")
    if mean_conf is not None and mean_conf < low_confidence:
        flags.append("low_confidence")
    if questions and PASSAGE_START.search(questions[0].text):
        flags.append("case_study")
    return {
        "n_questions": len(questions),
        "marks_total": total,
        "n_missing_marks": missing,
        "max_marks": max_marks,
        "number_jumps": jumps,
        "mean_conf": mean_conf,
        "flags": flags,
    }
