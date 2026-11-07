"""Year-wise summaries of topics and difficulty (Phase 7)."""

import pandas as pd


def topic_share_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Return each topic's share of questions per year and exam type."""
    raise NotImplementedError


def difficulty_mix_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Return the Easy/Medium/Hard mix per year."""
    raise NotImplementedError


def recurring_concepts(df: pd.DataFrame, min_years: int = 3) -> pd.DataFrame:
    """Return concepts that appear in at least min_years different years."""
    raise NotImplementedError
