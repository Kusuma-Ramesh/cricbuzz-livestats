"""Read-side analytics used by the dashboard pages (all SQL lives here or in utils/queries.py)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.db_connection import run_query, scalar

TTL = 300


@st.cache_data(ttl=TTL, show_spinner=False)
def kpis() -> dict:
    return {
        "players": int(scalar("SELECT COUNT(*) FROM players", default=0)),
        "matches": int(scalar("SELECT COUNT(*) FROM matches", default=0)),
        "runs": int(scalar("SELECT COALESCE(SUM(runs),0) FROM batting_performances", default=0)),
        "wickets": int(
            scalar("SELECT COALESCE(SUM(wickets),0) FROM bowling_performances", default=0)
        ),
        "venues": int(scalar("SELECT COUNT(*) FROM venues", default=0)),
        "series": int(scalar("SELECT COUNT(*) FROM series", default=0)),
        "sixes": int(scalar("SELECT COALESCE(SUM(sixes),0) FROM batting_performances", default=0)),
        "centuries": int(
            scalar("SELECT COUNT(*) FROM batting_performances WHERE runs >= 100", default=0)
        ),
    }


@st.cache_data(ttl=TTL, show_spinner=False)
def recent_results(n: int = 8) -> pd.DataFrame:
    return run_query(
        "SELECT m.match_date, m.match_format, t1.short_name AS t1, t2.short_name AS t2, w.short_name AS winner, "
        "m.victory_margin, m.victory_type, v.venue_name FROM matches m "
        "JOIN teams t1 ON t1.team_id=m.team1_id JOIN teams t2 ON t2.team_id=m.team2_id "
        "JOIN teams w ON w.team_id=m.winner_id JOIN venues v ON v.venue_id=m.venue_id "
        "ORDER BY m.match_date DESC, m.match_id DESC LIMIT " + str(int(n))
    )



@st.cache_data(ttl=TTL, show_spinner=False)
def team_table() -> pd.DataFrame:
    """Team win totals from matches with a recorded winner."""
    return run_query(
        "WITH s AS ("
        "SELECT team1_id AS team_id, winner_id FROM matches "
        "WHERE winner_id IS NOT NULL "
        "UNION ALL "
        "SELECT team2_id AS team_id, winner_id FROM matches "
        "WHERE winner_id IS NOT NULL"
        ") "
        "SELECT t.team_name, t.short_name, "
        "COUNT(*) AS played, "
        "SUM(CASE WHEN s.winner_id = s.team_id THEN 1 ELSE 0 END) AS won "
        "FROM s JOIN teams t ON t.team_id = s.team_id "
        "GROUP BY t.team_id, t.team_name, t.short_name "
        "ORDER BY won DESC"
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def team_form(n: int = 6) -> dict[str, list[str]]:
    """Return the latest completed-match results for each team."""
    df = run_query(
        "SELECT t.short_name, m.match_date, m.match_id, "
        "CASE "
        "WHEN m.winner_id = t.team_id THEN 'W' "
        "WHEN m.winner_id IS NULL THEN 'NR' "
        "ELSE 'L' END AS r "
        "FROM matches m "
        "JOIN teams t ON t.team_id IN (m.team1_id, m.team2_id) "
        "WHERE m.winner_id IS NOT NULL "
        "ORDER BY m.match_date DESC, m.match_id DESC"
    )

    out: dict[str, list[str]] = {}
    for short, g in df.groupby("short_name"):
        out[short] = g["r"].head(n).tolist()[::-1]
    return out


@st.cache_data(ttl=TTL, show_spinner=False)
def runs_by_format_year() -> pd.DataFrame:
    return run_query(
        "SELECT m.match_year AS year, m.match_format AS format, SUM(b.runs) * 1.0 / COUNT(DISTINCT m.match_id) AS runs_per_match "
        "FROM batting_performances b JOIN matches m ON m.match_id = b.match_id GROUP BY m.match_year, m.match_format "
        "ORDER BY m.match_year"
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def format_split() -> pd.DataFrame:
    return run_query(
        "SELECT match_format AS format, COUNT(*) AS matches FROM matches GROUP BY match_format"
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def venue_scoring(min_matches: int = 8) -> pd.DataFrame:
    """Average ODI innings total per venue (pre-aggregated per innings, then averaged: portable SQL)."""
    return run_query(
        "SELECT v.venue_name, v.city, v.country, COUNT(DISTINCT t.match_id) AS matches, AVG(t.total * 1.0) AS avg_innings_total "
        "FROM (SELECT b.match_id, b.innings_no, SUM(b.runs) AS total FROM batting_performances b GROUP BY b.match_id, b.innings_no) t "
        "JOIN matches m ON m.match_id = t.match_id JOIN venues v ON v.venue_id = m.venue_id "
        "WHERE m.match_format = 'ODI' GROUP BY v.venue_id, v.venue_name, v.city, v.country "
        "HAVING COUNT(DISTINCT t.match_id) >= "
        + str(int(min_matches))
        + " ORDER BY avg_innings_total DESC"
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def run_heatmap() -> pd.DataFrame:
    """Average runs scored by batting position x format (the 'batting order heat')."""
    return run_query(
        "SELECT b.batting_position AS position, m.match_format AS format, AVG(b.runs * 1.0) AS avg_runs "
        "FROM batting_performances b JOIN matches m ON m.match_id=b.match_id GROUP BY b.batting_position, m.match_format"
    )


# ------------------------------------------------------------------ player ratings
@st.cache_data(ttl=TTL, show_spinner=False)
def player_ratings() -> pd.DataFrame:
    """FIFA-style 0-99 ratings built from the Q21 weighting, scaled by percentile within the squad pool."""
    df = run_query(
        "SELECT p.player_id, p.full_name, p.country, p.playing_role, "
        "SUM(c.total_runs) AS runs, SUM(c.total_wickets) AS wickets, SUM(c.matches) AS matches, "
        "SUM(c.catches) AS catches, SUM(c.stumpings) AS stumpings, "
        "SUM(c.total_runs) * 1.0 / NULLIF(SUM(c.innings - c.not_outs), 0) AS bat_avg, "
        "AVG(c.strike_rate) AS strike_rate, AVG(c.economy_rate) AS economy, AVG(c.bowling_average) AS bowl_avg "
        "FROM players p JOIN player_career_stats c ON c.player_id = p.player_id "
        "GROUP BY p.player_id, p.full_name, p.country, p.playing_role"
    )
    if df.empty:
        return df
    pct = lambda s, inv=False: s.rank(pct=True, ascending=not inv).fillna(0)
    df["BAT"] = (
        (45 + 54 * (0.6 * pct(df.runs) + 0.4 * pct(df.bat_avg.fillna(0)))).round().astype(int)
    )
    df["BWL"] = (
        (
            45
            + 54
            * (0.6 * pct(df.wickets) + 0.4 * pct(df.economy.fillna(df.economy.max()), inv=True))
        )
        .round()
        .astype(int)
    )
    df["FLD"] = (45 + 54 * pct(df.catches + 2 * df.stumpings)).round().astype(int)
    w = df.playing_role.map(
        {
            "Batsman": (0.8, 0.0, 0.2),
            "Wicket-keeper": (0.55, 0.0, 0.45),
            "All-rounder": (0.45, 0.4, 0.15),
            "Bowler": (0.1, 0.8, 0.1),
        }
    )
    df["OVR"] = [
        int(round(b * x + o * y + f * z)) for b, o, f, (x, y, z) in zip(df.BAT, df.BWL, df.FLD, w)
    ]
    return df.sort_values("OVR", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=TTL, show_spinner=False)
def player_list() -> pd.DataFrame:
    return run_query(
        "SELECT player_id, full_name, country, playing_role FROM players ORDER BY full_name"
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def player_profile(player_id: int) -> dict:
    info = run_query("SELECT * FROM players WHERE player_id = :p", {"p": player_id})
    stats = run_query(
        "SELECT * FROM player_career_stats WHERE player_id = :p ORDER BY match_format",
        {"p": player_id},
    )
    last = run_query(
        "SELECT m.match_date, m.match_format, b.runs, b.balls_faced, b.is_out FROM batting_performances b "
        "JOIN matches m ON m.match_id=b.match_id WHERE b.player_id = :p ORDER BY m.match_date DESC, b.perf_id DESC LIMIT 15",
        {"p": player_id},
    )
    return {
        "info": info.iloc[0].to_dict() if not info.empty else {},
        "stats": stats,
        "last": last.iloc[::-1].reset_index(drop=True),
    }
