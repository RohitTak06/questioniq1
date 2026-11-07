"""Clean question text for the topic and difficulty models (Phase 2)."""


def clean_tokens(text: str, extra_stopwords: set[str]) -> list[str]:
    """Lowercase, tokenize, remove stopwords and short or numeric tokens, and lemmatize."""
    raise NotImplementedError
