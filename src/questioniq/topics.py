"""Discover topics with LDA and benchmark them against NMF (Phase 3)."""

from typing import Any

import pandas as pd
from sklearn.decomposition import NMF, LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer


def fit_lda(
    docs: list[str], k: int, random_state: int
) -> tuple[LatentDirichletAllocation, CountVectorizer]:
    """Fit LDA with k topics on raw word counts."""
    raise NotImplementedError


def fit_nmf(docs: list[str], k: int, random_state: int) -> tuple[NMF, TfidfVectorizer]:
    """Fit NMF with k topics on TF-IDF."""
    raise NotImplementedError


def coherence_cv(topics: list[list[str]], texts: list[list[str]]) -> float:
    """Return the C_v coherence of the topics' top words, computed with gensim."""
    raise NotImplementedError


def sweep_k(docs: list[str], k_min: int, k_max: int) -> pd.DataFrame:
    """Return C_v for LDA and NMF at every k from k_min to k_max."""
    raise NotImplementedError


def top_keywords(model: Any, feature_names: list[str], n: int = 10) -> list[list[str]]:
    """Return the n highest-weighted words of each topic."""
    raise NotImplementedError
