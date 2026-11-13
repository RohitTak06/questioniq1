"""Preprocessing rules. All text here is made up for the test; none is a real exam."""

from questioniq.preprocess import (
    clean_question,
    clean_tokens,
    lemmatize,
    normalise,
    stopword_set,
    tokenize,
)

EXAM_WORDS = {"explain", "discuss", "marks", "question"}


def test_normalise_lowercases_and_removes_ocr_debris() -> None:
    assert normalise("| Fake “Routing” _Table_ |") == "  fake  routing   table   "


def test_tokens_start_with_a_letter_so_pure_numbers_are_dropped() -> None:
    assert tokenize("IPv4 header of 2024, 15 bytes") == ["ipv4", "header", "of", "bytes"]


def test_lemmatizer_reads_words_as_nouns() -> None:
    assert [lemmatize(w) for w in ["networks", "algorithms", "matrices"]] == [
        "network",
        "algorithm",
        "matrix",
    ]


def test_stopwords_include_nltk_english_and_the_exam_words() -> None:
    stop = stopword_set(frozenset(EXAM_WORDS))
    assert {"the", "which", "explain", "marks"} <= stop


def test_lemmas_of_stopwords_are_stopwords_too() -> None:
    # WordNet turns "discuss" into "discus", which must not survive as a topic word.
    assert "discus" in stopword_set(frozenset(EXAM_WORDS))


def test_inflected_exam_verbs_are_dropped() -> None:
    assert clean_tokens("Discusses and explained fake routing", EXAM_WORDS) == ["fake", "routing"]


def test_content_words_are_not_cut_to_their_verb() -> None:
    assert clean_tokens("Fake machine learning and testing", EXAM_WORDS) == [
        "fake",
        "machine",
        "learning",
        "testing",
    ]


def test_clean_tokens_drops_stopwords_short_words_and_outcome_labels() -> None:
    text = "Explain the TCP handshake with an example. (CO2) [5 marks]"
    assert clean_tokens(text, EXAM_WORDS | {"example"}) == ["tcp", "handshake"]


def test_min_length_is_applied_after_lemmatizing() -> None:
    assert clean_tokens("Fake oxen", set(), min_length=3) == ["fake"]  # oxen -> ox


def test_clean_question_joins_tokens_and_keeps_order() -> None:
    assert clean_question("Discuss binary search trees and heaps.", EXAM_WORDS) == (
        "binary search tree heap"
    )


def test_empty_or_junk_text_gives_empty_string() -> None:
    assert clean_question("| __ 12 . ; |", EXAM_WORDS) == ""
