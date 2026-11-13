"""Clean question text for the topic models (Phase 2).

The steps: lowercase, remove OCR debris, split into words, drop stopwords (NLTK's
English list plus exam words from config.yaml), lemmatize with WordNet, then drop
short tokens and stopwords again. The raw text is never changed; the cleaned text is
stored next to it.
"""

import re
from functools import lru_cache

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import RegexpTokenizer

DEBRIS = re.compile(r"[|_~\"`*•¢©®«»“”‘’—–]")  # table rules and quote marks left by OCR
TOKENIZER = RegexpTokenizer(r"[a-z][a-z0-9]*")  # a word starts with a letter, so 2024 is dropped
OUTCOME_LABEL = re.compile(r"^[cl]o\d+$")  # co1, lo3: course-outcome labels, not content
LEMMATIZER = WordNetLemmatizer()


def normalise(text: str) -> str:
    """Lowercase the text and replace OCR debris with spaces."""
    return DEBRIS.sub(" ", text.lower())


def tokenize(text: str) -> list[str]:
    """Split text into words that start with a letter, after normalising it."""
    return TOKENIZER.tokenize(normalise(text))


@lru_cache(maxsize=None)
def lemmatize(word: str) -> str:
    """Return the WordNet lemma of a word, read as a noun (networks -> network)."""
    return LEMMATIZER.lemmatize(word)


@lru_cache(maxsize=8)
@lru_cache(maxsize=None)
def verb_lemma(word: str) -> str:
    """Return the WordNet lemma of a word read as a verb (explained -> explain)."""
    return LEMMATIZER.lemmatize(word, pos="v")


def is_stopword(word: str, stop: frozenset[str]) -> bool:
    """Return True if a word, or its verb form, is a stopword (discusses -> discuss).

    The verb form is only used to remove words. Kept words are lemmatized as nouns,
    so content words like "learning" or "testing" are not cut down to "learn" or "test".
    """
    return word in stop or verb_lemma(word) in stop


def stopword_set(extra_stopwords: frozenset[str]) -> frozenset[str]:
    """Return NLTK's English stopwords plus the extra words, and the lemmas of all of them.

    The lemmas are added because WordNet turns some stopwords into other words,
    for example "discuss" -> "discus", which would otherwise slip through.
    """
    words = set(stopwords.words("english")) | {word.lower() for word in extra_stopwords}
    return frozenset(words | {lemmatize(word) for word in words})


def clean_tokens(text: str, extra_stopwords: set[str], min_length: int = 3) -> list[str]:
    """Lowercase, tokenize, remove stopwords and short or numeric tokens, and lemmatize."""
    stop = stopword_set(frozenset(extra_stopwords))
    kept = [word for word in tokenize(text) if not is_stopword(word, stop) and not OUTCOME_LABEL.match(word)]
    lemmas = [lemmatize(word) for word in kept]
    return [lemma for lemma in lemmas if len(lemma) >= min_length and lemma not in stop]


def clean_question(text: str, extra_stopwords: set[str], min_length: int = 3) -> str:
    """Return the cleaned text of one question as space-separated tokens."""
    return " ".join(clean_tokens(text, extra_stopwords, min_length))
