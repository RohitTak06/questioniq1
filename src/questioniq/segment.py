"""Split a paper's text into individual questions (Phase 1)."""

from dataclasses import dataclass


@dataclass
class Question:
    """One question or sub-part, with its marks and course outcome if found."""

    qno: str
    sub_part: str | None
    text: str
    marks: int | None
    co: str | None


def segment(text: str) -> list[Question]:
    """Split paper text into questions using numbering rules."""
    raise NotImplementedError


def parse_marks(line: str) -> int | None:
    """Return the marks written on a line, or None if there are none."""
    raise NotImplementedError


def is_instruction(line: str) -> bool:
    """Return True for headers and instructions, which are not questions."""
    raise NotImplementedError
