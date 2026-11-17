"""Topic modelling. Every document here is made-up words in three clear themes."""

import joblib
import numpy as np
import pandas as pd

from questioniq.topics import (
    best_k,
    choose_model,
    coherence_cv,
    dominant_topics,
    fit_lda,
    fit_nmf,
    ngram_tokens,
    subject_alignment,
    sweep_k,
    top_keywords,
    topic_by_group,
    topic_distribution,
)

THEMES = {
    "net": "router packet subnet routing protocol tcp",
    "tree": "node tree heap binary insert traverse",
    "mat": "matrix eigenvalue vector basis rank determinant",
}
DOCS = [" ".join(np.random.default_rng(i).permutation(words.split())) for i in range(12) for words in THEMES.values()]
SETTINGS = {"k_min": 2, "k_max": 4, "top_n": 5, "min_df": 2, "ngram_range": [1, 2],
            "lda_max_iter": 50, "nmf_max_iter": 500}


def test_ngram_tokens_add_word_pairs() -> None:
    assert ngram_tokens("binary search tree") == ["binary", "search", "tree", "binary_search", "search_tree"]
    assert ngram_tokens("binary search", max_n=1) == ["binary", "search"]


def theme_of(words: list[str]) -> str:
    """Return the theme most of a topic's top words come from."""
    counts = {name: sum(word.split("_")[0] in vocab.split() for word in words) for name, vocab in THEMES.items()}
    return max(counts, key=counts.get)


def test_both_models_find_the_three_themes() -> None:
    for fit in (fit_lda, fit_nmf):
        model, vectorizer = fit(DOCS, 3, 42)
        topics = top_keywords(model, list(vectorizer.get_feature_names_out()), 5)
        assert sorted(theme_of(topic) for topic in topics) == ["mat", "net", "tree"]


def test_models_are_repeatable_with_the_same_seed() -> None:
    first, _ = fit_lda(DOCS, 3, 42)
    second, _ = fit_lda(DOCS, 3, 42)
    assert np.allclose(first.components_, second.components_)


def test_fitted_vectorizer_can_be_saved(tmp_path) -> None:
    _, vectorizer = fit_nmf(DOCS, 3, 42)
    joblib.dump(vectorizer, tmp_path / "v.joblib")
    assert joblib.load(tmp_path / "v.joblib").transform(DOCS[:1]).shape[0] == 1


def test_coherent_topics_score_higher_than_mixed_ones() -> None:
    texts = [doc.split() for doc in DOCS]
    clean = [vocab.split()[:4] for vocab in THEMES.values()]
    mixed = [[THEMES[name].split()[i] for name in THEMES] + [THEMES["net"].split()[5]] for i in range(3)]
    assert coherence_cv(clean, texts) > coherence_cv(mixed, texts)


def test_sweep_scores_every_k_for_both_models() -> None:
    sweep = sweep_k(DOCS, SETTINGS, 42)
    assert sorted(zip(sweep["model"], sweep["k"])) == [(m, k) for m in ("lda", "nmf") for k in (2, 3, 4)]
    assert sweep["c_v"].between(0, 1).all()


def test_best_k_prefers_the_smaller_k_on_a_tie_and_the_higher_model_wins() -> None:
    sweep = pd.DataFrame({"model": ["lda", "lda", "nmf", "nmf"], "k": [4, 5, 4, 5], "c_v": [0.5, 0.5, 0.4, 0.6]})
    best = best_k(sweep)
    assert best == {"lda": {"k": 4, "c_v": 0.5}, "nmf": {"k": 5, "c_v": 0.6}}
    assert choose_model(best) == "nmf"
    assert choose_model({"lda": {"k": 4, "c_v": 0.5}, "nmf": {"k": 5, "c_v": 0.5}}) == "lda"


def test_distribution_rows_sum_to_one_and_dominant_topic_is_numbered_from_one() -> None:
    model, vectorizer = fit_nmf(DOCS, 3, 42)
    distribution = topic_distribution(model, vectorizer, DOCS + ["unknownword"])
    assert np.allclose(distribution[:-1].sum(axis=1), 1)
    assert distribution[-1].sum() == 0
    dominant = dominant_topics(distribution)
    assert set(dominant[:-1]) == {1, 2, 3} and dominant[-1] == 0


def test_topic_by_department_counts_and_alignment() -> None:
    dominant = [1, 1, 1, 2, 2, 2]
    groups = ["CS", "CS", "AS", "AS", "AS", "AS"]
    table = topic_by_group(dominant, groups)
    assert table.loc["CS", 1] == 2 and table.loc["AS", 2] == 3
    alignment = subject_alignment(dominant, groups)
    assert alignment["per_topic"][1] == {"top_department": "CS", "top_share": 0.667, "n_questions": 3}
    assert 0 < alignment["nmi"] < 1


def test_question_topic_rows_hold_ids_and_shares_but_no_text() -> None:
    from scripts.run_topics import keyword_rows, question_topic_rows

    question = {"question_id": "7-1", "paper_id": "7", "course": "XX1", "year": "2024",
                "exam_type": "Endterm", "text": "Fake secret text"}
    rows = question_topic_rows([question], "nmf", np.array([[0.25, 0.75]]), [2])
    assert rows == [{"question_id": "7-1", "paper_id": "7", "course": "XX1", "year": "2024",
                     "exam_type": "Endterm", "model": "nmf", "dominant_topic": 2,
                     "topic_1": 0.25, "topic_2": 0.75}]
    assert keyword_rows("nmf", 2, [["a", "b"], ["c"]])[1] == {"model": "nmf", "k": 2, "topic": 2, "keywords": "c"}
