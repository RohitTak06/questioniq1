"""Turn a question into human-readable features for the difficulty model (Phase 5)."""

from questioniq.segment import Question


def bloom_level(text: str, bloom_verbs: dict[str, int]) -> int:
    """Return the highest Bloom's Taxonomy level among the question's action verbs."""
    raise NotImplementedError


def extract_features(question: Question, dominant_topic: int) -> dict[str, float]:
    """Return the feature values for one question, keyed by feature name."""
    raise NotImplementedError
