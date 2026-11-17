"""Year-wise summaries of topics and difficulty (Phase 7).

Each function takes a plain table with one row per question and returns a summary table.
Every summary keeps the number of questions behind it, because the papers are very uneven
across years and a share from 9 questions means much less than one from 600.
"""

import pandas as pd

GRADES = ["Easy", "Medium", "Hard"]


def topic_share_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Return each topic's share of questions per year and exam type.

    df needs year, exam_type and dominant_topic. Questions with no topic (0) are left out.
    Columns: year, exam_type, topic, n_questions (in the topic), year_total, share.
    """
    with_topic = df[df["dominant_topic"] > 0]
    counts = with_topic.groupby(["year", "exam_type", "dominant_topic"]).size().rename("n_questions").reset_index()
    totals = with_topic.groupby(["year", "exam_type"]).size().rename("year_total").reset_index()
    table = counts.merge(totals, on=["year", "exam_type"]).rename(columns={"dominant_topic": "topic"})
    table["share"] = (table["n_questions"] / table["year_total"]).round(3)
    return table.sort_values(["year", "exam_type", "share"], ascending=[True, True, False]).reset_index(drop=True)


def difficulty_mix_by_year(df: pd.DataFrame, column: str = "difficulty") -> pd.DataFrame:
    """Return the Easy/Medium/Hard mix per year.

    df needs year and a column of Easy/Medium/Hard values (other values are left out).
    Columns: year, n_questions, then the share of each grade.
    """
    graded = df[df[column].isin(GRADES)]
    counts = pd.crosstab(graded["year"], graded[column]).reindex(columns=GRADES, fill_value=0)
    table = counts.div(counts.sum(axis=1), axis=0).round(3)
    table.insert(0, "n_questions", counts.sum(axis=1))
    return table.reset_index()


def recurring_concepts(df: pd.DataFrame, min_years: int = 3) -> pd.DataFrame:
    """Return concepts that appear in at least min_years different years.

    df needs year and concepts (a list of terms per question). Columns: concept, n_years,
    years (as text, such as "2022, 2023, 2024") and n_questions; most years first.
    """
    exploded = df[["year", "concepts"]].explode("concepts").dropna(subset=["concepts"])
    grouped = exploded.groupby("concepts").agg(
        n_years=("year", "nunique"),
        years=("year", lambda years: ", ".join(str(year) for year in sorted(set(years)))),
        n_questions=("year", "size"),
    )
    table = grouped[grouped["n_years"] >= min_years].reset_index().rename(columns={"concepts": "concept"})
    return table.sort_values(["n_years", "n_questions", "concept"], ascending=[False, False, True]).reset_index(drop=True)
