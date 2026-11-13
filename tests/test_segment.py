"""Segmentation rules. Every paper here is made up for the test; none is a real exam."""

import pytest

from questioniq.segment import (
    Question,
    check_paper,
    find_max_marks,
    is_instruction,
    leading_passage,
    marks_total,
    normalise_qno,
    number_jumps,
    paper_style,
    parse_co,
    parse_marks,
    segment,
    split_cells,
)


def q(qno: str, marks: float | None = 5, alternative: int = 0, sub: str | None = None) -> Question:
    return Question(qno, sub, "fake", marks, None, alternative)


@pytest.mark.parametrize("raw, expected", [("1", "1"), ("I", "1"), ("l", "1"), ("1O", "10"), ("12", "12")])
def test_normalise_qno(raw: str, expected: str) -> None:
    assert normalise_qno(raw) == expected


def test_split_cells_removes_table_rules() -> None:
    assert split_cells("~ QI. | Let X be fake |\t1") == ("QI. Let X be fake", "1")


@pytest.mark.parametrize(
    "cell, expected",
    [
        ("5", 5.0),
        ("10.0", 10.0),
        ("1.5", 1.5),
        ("[5]", 5.0),
        ("[5", 5.0),
        ("(5 marks)", 5.0),
        ("5 marks", 5.0),
        ("5M", 5.0),
        ("10.0 (LO3)", 10.0),
        ("4x3", 12.0),
        ("Explain the fake idea. 2+4", 6.0),
        ("Fake question (7 marks) (CO-1)", 7.0),
        ("CO1,2", None),
        ("h00", None),
        ("", None),
        ("Find the value of x", None),
    ],
)
def test_parse_marks(cell: str, expected: float | None) -> None:
    assert parse_marks(cell) == expected


@pytest.mark.parametrize(
    "cell, expected",
    [
        ("CO1", "CO1"),
        ("COl", "CO1"),
        ("C01", "CO1"),
        ("CO1,2", "CO1,2"),
        ("(L03)", "LO3"),
        ("IO2", "LO2"),
        ("(CO-1)", "CO1"),
        ("5", None),
    ],
)
def test_parse_co(cell: str, expected: str | None) -> None:
    assert parse_co(cell) == expected


@pytest.mark.parametrize(
    "line",
    ["1. Do not write anything other than your roll number.", "2. Use of calculators is allowed.", "Attempt any five."],
)
def test_is_instruction_finds_instructions(line: str) -> None:
    assert is_instruction(line)


def test_is_instruction_leaves_questions_alone() -> None:
    assert not is_instruction("Compare two fake sorting methods with examples.")


@pytest.mark.parametrize(
    "start",
    ["Q1.", "Q.1", "Q 1", "Q1)", "QI.", "Ql.", "| Q.1 |", "/Q1 |", "~ QI. |", "Question 1", "Ques. 1", "Q’ 1"],
)
def test_all_question_number_forms_start_a_question(start: str) -> None:
    text = f"{start} Fake first question\t5\nQ2. Fake second question\t5"
    questions = segment(text)
    assert [question.qno for question in questions] == ["1", "2"]
    assert questions[0].text == "Fake first question"


def test_words_starting_with_q_are_not_question_numbers() -> None:
    assert len(segment("Q1. Fake\t5\nQuality matters here.\nQ2. Fake\t5")) == 2


def test_lines_before_the_first_question_are_not_questions() -> None:
    text = (
        "Fake University\nMax. Marks: 10\nInstructions to students:\n"
        "1. Do not write anything other than your roll number.\n"
        "Q1. Fake one\t5\nQ2. Fake two\t5"
    )
    questions = segment(text)
    assert [question.text for question in questions] == ["Fake one", "Fake two"]


def test_question_continues_over_lines_and_pages_without_page_markers() -> None:
    text = "Q1. Fake start\t5\nof the question\nPage 1 of 2\nand its end\nQ2. Fake two\t5"
    assert segment(text)[0].text == "Fake start of the question and its end"


def test_misread_number_is_kept_and_not_guessed() -> None:
    questions = segment("Q4. Fake\t3\nQ35. Fake\t3\nQ6. Fake\t5")
    assert [question.qno for question in questions] == ["4", "35", "6"]


def test_marks_and_co_on_separate_lines_are_both_found() -> None:
    question = segment("Q1. Fake start\t5\nand end\tCOl\nQ2. Fake\t5")[0]
    assert (question.marks, question.co) == (5.0, "CO1")


def test_marks_in_the_body_are_found() -> None:
    assert segment("Q1. Fake question [5]\nQ2. Fake question (5 marks)")[1].marks == 5.0


def test_missing_marks_stay_none() -> None:
    assert segment("Q1. Fake\th00\nQ2. Fake\t5")[0].marks is None


def test_or_inside_a_question_gives_two_options_with_the_same_number() -> None:
    questions = segment("Q.1 Fake first option\t10.0\nOR\nFake second option\t10.0\nQ.2 Fake\t10.0")
    assert [(q.qno, q.alternative) for q in questions] == [("1", 1), ("1", 2), ("2", 0)]
    assert questions[1].text == "Fake second option"


def test_or_between_numbered_questions_links_them_as_options() -> None:
    questions = segment("Q1. Fake\t5\nOR\nQ2. Fake\t5\nQ3. Fake\t5")
    assert [(q.qno, q.alternative) for q in questions] == [("1", 1), ("2", 2), ("3", 0)]


def test_sub_parts_with_their_own_marks_become_rows_sharing_the_stem() -> None:
    text = "Q1. Fake shared stem\n(a) Fake part one\t2\n(b) Fake part two\t3\nQ2. Fake\t5"
    questions = segment(text)
    assert [(q.qno, q.sub_part, q.marks) for q in questions] == [
        ("1", "a", 2.0),
        ("1", "b", 3.0),
        ("2", None, 5.0),
    ]
    assert questions[0].text == "Fake shared stem Fake part one"


def test_sub_parts_without_their_own_marks_stay_one_row() -> None:
    text = "Q1. Fake stem\t3\n1. Fake part one\n2. Fake part two\n3. Fake part three\nQ2. Fake\t5"
    questions = segment(text)
    assert [(q.qno, q.sub_part, q.marks) for q in questions] == [("1", None, 3.0), ("2", None, 5.0)]
    assert "Fake part three" in questions[0].text


def test_some_marked_sub_parts_stay_one_row_with_their_sum() -> None:
    questions = segment("Q1. Fake stem\n(a) Fake one\t2\n(b) Fake two\t3\n(c) Fake three\nQ2. Fake\t5")
    assert (questions[0].sub_part, questions[0].marks) == (None, 5.0)


def test_mcq_options_stay_in_the_question_text() -> None:
    text = "Q1. Fake multiple choice\t1\nA. fake\nB. fake\nC. fake\nD. fake\nQ2. Fake\t1"
    assert len(segment(text)) == 2


def test_a_stray_letter_label_out_of_order_is_left_in_the_text() -> None:
    questions = segment("Q1. Fake\t5\n(c) Fake stray\nQ2. Fake\t5")
    assert (len(questions), questions[0].sub_part) == (2, None)
    assert "Fake stray" in questions[0].text


def test_q1a_style_keeps_the_letter() -> None:
    questions = segment("Q.1A Fake\t5\nQ.1B Fake\t5")
    assert [(q.qno, q.sub_part) for q in questions] == [("1", "A"), ("1", "B")]


def test_numbered_paper_skips_numbered_instructions_with_unknown_wording() -> None:
    text = (
        "Instructions:\n1. Mention your fake details.\n2. Keep fake things neat.\n"
        "1. Fake real question\t5\n2. Fake real two\t5"
    )
    assert [q.text for q in segment(text)] == ["Fake real question", "Fake real two"]


def test_numbered_paper_ignores_numbers_that_jump_far_ahead() -> None:
    text = "1. Fake one\t5\n45. fake data line\n2. Fake two\t5"
    questions = segment(text)
    assert [q.qno for q in questions] == ["1", "2"]
    assert "fake data line" in questions[0].text


def test_numbered_paper_allows_a_small_skip() -> None:
    assert [q.qno for q in segment("1. Fake\t5\n2. Fake\t5\n4. Fake\t5")] == ["1", "2", "4"]


def test_numbered_paper_accepts_a_comma_misread_for_a_period() -> None:
    assert [q.qno for q in segment("1. Fake\t5\n2, Fake\t5")] == ["1", "2"]


def test_numbered_paper_accepts_bare_numbers() -> None:
    assert [q.qno for q in segment("1. Fake\t5\n2 Fake with no period\t5")] == ["1", "2"]


def test_numbered_steps_inside_a_question_do_not_restart_without_an_instructions_header() -> None:
    text = "1. Fake first\t5\n2. Fake second\n1. fake step\n2. fake step\n3. Fake third\t5"
    assert [q.qno for q in segment(text)] == ["1", "2", "3"]


def test_only_one_restart_is_allowed_after_an_instructions_header() -> None:
    text = (
        "Instructions:\n1. Keep fake things neat.\n1. Fake first\n2. Fake second\n"
        "1. fake step\n3. Fake third"
    )
    questions = segment(text)
    assert [q.qno for q in questions] == ["1", "2", "3"]
    assert "fake step" in questions[1].text


def test_number_with_letter_keeps_both_and_may_repeat_the_number() -> None:
    questions = segment("1(a). Fake one (7 marks)\n1(b). Fake two (3 marks)\n2. Fake three (5 marks)")
    assert [(q.qno, q.sub_part, q.marks) for q in questions] == [
        ("1", "a", 7.0),
        ("1", "b", 3.0),
        ("2", None, 5.0),
    ]


def test_a_single_numbered_question_still_counts() -> None:
    assert [q.qno for q in segment("1. Fake only question\t5")] == ["1"]


def test_misread_q_counts_only_as_exactly_the_next_number() -> None:
    questions = segment("Q1. Fake\t5\n(O2 Fake misread\t5\n0.8 is a fake decimal\nQ3. Fake\t5")
    assert [q.qno for q in questions] == ["1", "2", "3"]
    assert "0.8 is a fake decimal" in questions[1].text


def test_data_table_rows_are_not_misread_question_numbers() -> None:
    questions = segment("Q1. Fake\t5\n002 49 M 470001\nQ2. Fake\t5")
    assert [q.qno for q in questions] == ["1", "2"]
    assert "002 49 M 470001" in questions[0].text


def test_lost_q_counts_only_as_exactly_the_next_number() -> None:
    questions = segment("Q1. Fake\t5\n2 Fake lost Q\t5\n7 Fake not next\nQ3. Fake\t5")
    assert [q.qno for q in questions] == ["1", "2", "3"]
    assert "7 Fake not next" in questions[1].text


def test_table_paper_finds_bare_numbers() -> None:
    text = "Sr.No Question Marks CO\n1 Fake first question\t5\n2 Fake second question\t5"
    questions = segment(text)
    assert [q.qno for q in questions] == ["1", "2"]
    assert questions[1].text == "Fake second question"


def test_paper_with_no_numbering_gives_no_questions() -> None:
    assert segment("A fake paragraph with nothing numbered.\nAnother fake line.") == []


def test_empty_text_gives_no_questions() -> None:
    assert segment("") == []


def test_case_study_passage_stays_with_the_first_question() -> None:
    text = "Fake header\nCase Study: 30 marks\nBackground: a fake firm.\n1. Fake question one\t15\n2. Fake two\t15"
    questions = segment(text)
    assert questions[0].text.startswith("Case Study")
    assert questions[0].text.endswith("Fake question one")
    assert not questions[1].text.startswith("Case Study")


def test_leading_passage_ignores_ordinary_headers() -> None:
    assert leading_passage(["Fake University", "Time: 2 hours"]) == ""


@pytest.mark.parametrize(
    "bodies, expected",
    [
        (["Q1. fake", "Q2. fake"], "q"),
        (["Sr.No Question Marks", "1 Fake"], "table"),
        (["1. Fake", "2. Fake"], "number"),
        (["Q1. fake"], "q"),
        (["fake"], "none"),
    ],
)
def test_paper_style(bodies: list[str], expected: str) -> None:
    assert paper_style(bodies) == expected


def test_marks_total_adds_ordinary_questions() -> None:
    assert marks_total([q("1", 2), q("2", 3.5)]) == (5.5, 0)


def test_marks_total_counts_only_the_largest_or_option() -> None:
    questions = [q("1", 10, 1), q("1", 12, 2), q("2", 5)]
    assert marks_total(questions) == (17.0, 0)


def test_marks_total_adds_sub_parts_within_one_or_option() -> None:
    questions = [q("1", 2, 1, "a"), q("1", 3, 1, "b"), q("1", 4, 2), q("2", 5)]
    assert marks_total(questions) == (10.0, 0)


def test_marks_total_treats_neighbouring_or_groups_separately() -> None:
    questions = [q("1", 5, 1), q("1", 5, 2), q("2", 5, 1), q("2", 5, 2)]
    assert marks_total(questions) == (10.0, 0)


def test_marks_total_counts_missing_marks() -> None:
    assert marks_total([q("1", None), q("2", 5)]) == (5.0, 1)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Time: 2 hours Max. Marks: 30", 30.0),
        ("Maximum Marks: 40 Time Allowed", 40.0),
        ("Max Marks\t50", 50.0),
        ("Time: 2 hours", None),
    ],
)
def test_find_max_marks(text: str, expected: float | None) -> None:
    assert find_max_marks(text) == expected


def test_number_jumps_reports_skips_without_changing_anything() -> None:
    assert number_jumps([q("7"), q("9"), q("9"), q("10")]) == ["7->9"]


def test_check_paper_passes_a_clean_paper() -> None:
    result = check_paper([q("1", 5), q("2", 5)], "Max. Marks: 10", 90.0, 70)
    assert result["flags"] == []
    assert (result["n_questions"], result["marks_total"]) == (2, 10.0)


@pytest.mark.parametrize(
    "questions, text, conf, flag",
    [
        ([], "Max. Marks: 10", 90.0, "no_questions"),
        ([q("1", None)], "Max. Marks: 10", 90.0, "missing_marks"),
        ([q("1", 5)], "no header", 90.0, "no_max_marks"),
        ([q("1", 5)], "Max. Marks: 10", 90.0, "marks_mismatch"),
        ([q("1", 5)], "Max. Marks: 10 Attempt any two", 90.0, "attempt_any"),
        ([q("1", 5), q("3", 5)], "Max. Marks: 10", 90.0, "number_jump"),
        ([q("1", 10)], "Max. Marks: 10", 50.0, "low_confidence"),
    ],
)
def test_check_paper_flags(questions: list[Question], text: str, conf: float, flag: str) -> None:
    assert flag in check_paper(questions, text, conf, 70)["flags"]


def test_check_paper_marks_equal_marks_papers_apart_from_missing_marks() -> None:
    flags = check_paper([q("1", None)], "Max. Marks: 10 All questions carry equal marks", 90.0, 70)["flags"]
    assert "equal_marks" in flags
    assert "missing_marks" not in flags


def test_check_paper_does_not_call_attempt_any_papers_a_mismatch() -> None:
    result = check_paper([q("1", 5), q("2", 5)], "Max. Marks: 5 Attempt any one", 90.0, 70)
    assert "marks_mismatch" not in result["flags"]


# --- Rules added after the first hand check (2026-11-13) ---


def labels(text: str) -> list[tuple[str, str | None]]:
    return [(question.qno, question.sub_part) for question in segment(text)]


def test_two_level_numbers_are_separate_questions() -> None:
    text = "Q.1.1 Fake\t3\nQ.1.2 Fake\t3\nQ.2.1 Fake\t3"
    assert labels(text) == [("1", "1"), ("1", "2"), ("2", "1")]


def test_two_level_number_with_q_read_as_zero() -> None:
    text = "Q.1.1 Fake\t3\nQ.1.2 Fake\t3\n0.2.1 Fake\t3\n0. 2.2 Fake\t3"
    assert labels(text) == [("1", "1"), ("1", "2"), ("2", "1"), ("2", "2")]


def test_number_read_as_a_letter_is_kept_and_flagged() -> None:
    questions = segment("Q1. Fake\t2\nQ.g Fake\t2\nQ3. Fake\t2")
    assert [question.qno for question in questions] == ["1", "g", "3"]
    assert "unreadable_qno" in check_paper(questions, "Max. Marks: 6", None, 70)["flags"]


def test_number_read_as_a_letter_needs_a_bigger_label_after_it() -> None:
    assert labels("Q1. Fake\t2\nQA Fake text\nQ2. Fake\t2") == [("1", None), ("2", None)]


def test_numbered_rows_are_not_lost_questions_when_the_same_question_continues() -> None:
    text = "Q4A. Fake table\t2\n5 Fake row\n6 Fake row\nQ4B. Fake\t2"
    assert labels(text) == [("4", "A"), ("4", "B")]


def test_far_misread_label_does_not_move_the_expected_number() -> None:
    assert [question.qno for question in segment("Q1. Fake\t1\nQ32. Fake\t1\n02 Fake\t1")] == [
        "1",
        "32",
        "2",
    ]


def test_marks_line_just_above_a_number_moves_to_that_question() -> None:
    questions = segment("Q.1 Fake\t3\nFake first line of two\t3\nQ.2 Fake second line")
    assert [question.text for question in questions] == [
        "Fake",
        "Fake first line of two Fake second line",
    ]


def test_marks_line_stays_when_it_is_a_labelled_part() -> None:
    questions = segment("Q.1 Fake\n(a) Fake\t2\n(b) Fake\t3\nQ.2 Fake second")
    assert [(q.qno, q.sub_part) for q in questions] == [("1", "a"), ("1", "b"), ("2", None)]


def test_marks_line_stays_when_the_start_line_has_its_own_marks() -> None:
    questions = segment("Q.1 Fake\t3\nFake more\t3\nQ.2 Fake\t4")
    assert questions[0].text == "Fake Fake more"


def test_number_followed_by_a_bare_letter_starts_a_question_with_parts() -> None:
    text = "Sr. No. Question Marks\n1. Fake one\t2\n2 a Fake part\t3\nb Fake part\t2\n3. Fake\t1"
    assert labels(text) == [("1", None), ("2", "a"), ("2", "b"), ("3", None)]


def test_page_footer_with_numbers_in_the_right_cell_is_dropped() -> None:
    assert segment("Q1. Fake\t2\nPage of\t1 3\nQ2. Fake\t2")[0].text == "Fake"


def test_co_label_in_brackets_is_not_marks() -> None:
    assert parse_marks("(LO1 3)") is None


def test_line_starting_with_the_same_number_as_the_label_below_joins_it() -> None:
    questions = segment("Q1. Fake one\t2\nFake more\n2 Fake first line\nQ2. Fake second line\t2")
    assert [question.text for question in questions] == [
        "Fake one Fake more",
        "Fake first line Fake second line",
    ]


def test_step_two_of_the_previous_question_stays_with_it() -> None:
    questions = segment("Q1. Fake stem\t2\n1. Fake step\n2. Fake step\nQ2. Fake\t2")
    assert questions[0].text == "Fake stem 1. Fake step 2. Fake step"
