"""Discover topics with LDA and benchmark them against NMF (Phase 3).

Both models read the cleaned question text as words plus adjacent word pairs
(binary_search, linked_list). LDA works on raw counts, since it models word counts;
NMF works on TF-IDF. Topic quality is C_v coherence, computed with gensim on each
topic's top words. Topics are numbered from 1 in everything the owner sees.
"""

from functools import partial
from typing import Any

import numpy as np
import pandas as pd
from gensim.corpora import Dictionary
from gensim.models.coherencemodel import CoherenceModel
from sklearn.decomposition import NMF, LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics import normalized_mutual_info_score

MODEL_KINDS = ("lda", "nmf")


def ngram_tokens(doc: str, max_n: int = 2) -> list[str]:
    """Return a cleaned text's words plus its word pairs joined by "_" (when max_n is 2)."""
    words = doc.split()
    if max_n < 2:
        return words
    return words + [f"{first}_{second}" for first, second in zip(words, words[1:])]


def _analyzer(max_n: int) -> partial:
    """Return the tokenizer the vectorizers use, so models and coherence see the same terms.

    A partial (not a lambda) so the fitted vectorizer can be saved with joblib.
    """
    return partial(ngram_tokens, max_n=max_n)


def fit_lda(
    docs: list[str], k: int, random_state: int, min_df: int = 2, max_n: int = 2, max_iter: int = 50
) -> tuple[LatentDirichletAllocation, CountVectorizer]:
    """Fit LDA with k topics on raw word counts."""
    vectorizer = CountVectorizer(analyzer=_analyzer(max_n), min_df=min_df)
    counts = vectorizer.fit_transform(docs)
    model = LatentDirichletAllocation(
        n_components=k, random_state=random_state, learning_method="batch", max_iter=max_iter
    )
    model.fit(counts)
    return model, vectorizer


def fit_nmf(
    docs: list[str], k: int, random_state: int, min_df: int = 2, max_n: int = 2, max_iter: int = 500
) -> tuple[NMF, TfidfVectorizer]:
    """Fit NMF with k topics on TF-IDF."""
    vectorizer = TfidfVectorizer(analyzer=_analyzer(max_n), min_df=min_df)
    weights = vectorizer.fit_transform(docs)
    model = NMF(n_components=k, init="nndsvda", random_state=random_state, max_iter=max_iter)
    model.fit(weights)
    return model, vectorizer


def fit_model(kind: str, docs: list[str], k: int, settings: dict, random_state: int) -> tuple[Any, Any]:
    """Fit LDA or NMF with the settings from config.yaml's topics section."""
    common = {"min_df": settings["min_df"], "max_n": settings["ngram_range"][1]}
    if kind == "lda":
        return fit_lda(docs, k, random_state, max_iter=settings["lda_max_iter"], **common)
    if kind == "nmf":
        return fit_nmf(docs, k, random_state, max_iter=settings["nmf_max_iter"], **common)
    raise ValueError(f"unknown model kind: {kind}")


def top_keywords(model: Any, feature_names: list[str], n: int = 10) -> list[list[str]]:
    """Return the n highest-weighted words of each topic."""
    return [[feature_names[i] for i in np.argsort(weights)[::-1][:n]] for weights in model.components_]


def coherence_cv(topics: list[list[str]], texts: list[list[str]]) -> float:
    """Return the C_v coherence of the topics' top words, computed with gensim.

    texts are the same tokens the models saw (words and word pairs), so every
    top word can be found in them. One process keeps the result repeatable.
    """
    dictionary = Dictionary(texts)
    model = CoherenceModel(topics=topics, texts=texts, dictionary=dictionary, coherence="c_v", processes=1)
    return float(model.get_coherence())


def sweep_k(docs: list[str], settings: dict, random_state: int) -> pd.DataFrame:
    """Return C_v for LDA and NMF at every k from k_min to k_max."""
    texts = [ngram_tokens(doc, settings["ngram_range"][1]) for doc in docs]
    rows = []
    for kind in MODEL_KINDS:
        for k in range(settings["k_min"], settings["k_max"] + 1):
            model, vectorizer = fit_model(kind, docs, k, settings, random_state)
            topics = top_keywords(model, list(vectorizer.get_feature_names_out()), settings["top_n"])
            rows.append({"model": kind, "k": k, "c_v": coherence_cv(topics, texts)})
    return pd.DataFrame(rows)


def best_k(sweep: pd.DataFrame) -> dict[str, dict]:
    """Return each model's k with the highest C_v (the smaller k on a tie) and that C_v."""
    best = {}
    for kind, rows in sweep.groupby("model"):
        top = rows.sort_values(["c_v", "k"], ascending=[False, True]).iloc[0]
        best[str(kind)] = {"k": int(top["k"]), "c_v": float(top["c_v"])}
    return best


def choose_model(best: dict[str, dict]) -> str:
    """Return the model kind whose best k has the higher C_v (LDA on a tie, as in the plan)."""
    return max(MODEL_KINDS, key=lambda kind: (best[kind]["c_v"], kind == "lda"))


def topic_distribution(model: Any, vectorizer: Any, docs: list[str]) -> np.ndarray:
    """Return each document's topic shares, one row per document, each row summing to 1.

    LDA already gives shares. NMF gives weights, which are divided by their row total;
    a document with no weight on any topic gets a row of zeros.
    """
    weights = model.transform(vectorizer.transform(docs))
    totals = weights.sum(axis=1, keepdims=True)
    return np.divide(weights, totals, out=np.zeros_like(weights), where=totals > 0)


def dominant_topics(distribution: np.ndarray) -> list[int]:
    """Return each document's main topic, numbered from 1, or 0 if it has no topic weight."""
    return [int(np.argmax(row)) + 1 if row.sum() > 0 else 0 for row in distribution]


def topic_by_group(dominant: list[int], groups: list[str]) -> pd.DataFrame:
    """Return how many documents of each group (such as a department) fall in each topic."""
    return pd.crosstab(pd.Series(groups, name="department"), pd.Series(dominant, name="topic"))


def subject_alignment(dominant: list[int], groups: list[str]) -> dict:
    """Return how strongly topics line up with subjects.

    nmi is the normalised mutual information between topic and department: 0 means
    topics ignore departments, 1 means each topic is exactly one department. Per topic,
    top_share is the share of its questions that come from its biggest department.
    """
    table = topic_by_group(dominant, groups)
    per_topic = {
        int(topic): {
            "top_department": str(table[topic].idxmax()),
            "top_share": round(float(table[topic].max() / table[topic].sum()), 3),
            "n_questions": int(table[topic].sum()),
        }
        for topic in table.columns
    }
    return {"nmi": round(float(normalized_mutual_info_score(groups, dominant)), 3), "per_topic": per_topic}
