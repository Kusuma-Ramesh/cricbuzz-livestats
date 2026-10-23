import re

import pytest

from utils.db_connection import run_query
from utils.queries import BY_NUMBER, Q, default_params


def test_exactly_25_questions():
    assert [q.number for q in Q] == list(range(1, 26))


@pytest.mark.parametrize("q", Q, ids=lambda q: f"Q{q.number:02d}")
def test_every_query_runs(q):
    df = run_query(q.sql, default_params())
    assert list(df.columns)
    assert len(df) > 0, f"Q{q.number} returned no rows on the demo dataset"


def test_only_requested_limits():
    limited = {q.number for q in Q if re.search(r"\bLIMIT\b", q.sql)}
    assert limited == {3, 10}, "only Q3 (top 10) and Q10 (last 20) ask for a row limit"


def test_q3_top10_sorted():
    df = run_query(BY_NUMBER[3].sql)
    assert len(df) == 10 and df.total_runs.is_monotonic_decreasing


def test_q23_counts_scores_strictly_above_50():
    sql = BY_NUMBER[23].sql
    assert "runs > 50" in sql and "runs >= 50" not in sql


def test_q23_categories_valid():
    df = run_query(BY_NUMBER[23].sql)
    assert set(df.form_category) <= {"Excellent Form", "Good Form", "Average Form", "Poor Form"}


def test_q17_percentage_matches_manual_count():
    df = run_query(BY_NUMBER[17].sql)
    manual = run_query(
        "SELECT SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) AS w, COUNT(*) AS n "
        "FROM matches WHERE winner_id IS NOT NULL AND toss_winner_id IS NOT NULL"
    )
    assert df.matches.sum() == manual.n.iloc[0]
    assert df.toss_winner_won.sum() == manual.w.iloc[0]


def test_q11_overall_average_uses_dismissals():
    df = run_query(BY_NUMBER[11].sql)
    row = df.iloc[0]
    c = run_query(
        "SELECT SUM(total_runs) AS r, SUM(innings - not_outs) AS d FROM player_career_stats c "
        "JOIN players p ON p.player_id = c.player_id WHERE p.full_name = :n",
        {"n": row.player},
    )
    assert abs(row.overall_batting_avg - round(c.r.iloc[0] / c.d.iloc[0], 2)) < 0.011


def test_economy_matches_legal_balls():
    bad = run_query(
        "SELECT COUNT(*) AS n FROM bowling_performances "
        "WHERE ABS(economy - runs_conceded * 6.0 / legal_balls) > 0.01"
    )
    assert bad.n.iloc[0] == 0
