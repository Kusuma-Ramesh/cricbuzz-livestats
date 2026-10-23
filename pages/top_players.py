"""Top Player Stats: podium + leaderboards from the Cricbuzz API (or the SQL database)."""

import pandas as pd
import streamlit as st

from api.cricbuzz_client import CricbuzzAPIError
from api.parsers import build_api_board
from services import live_service
from utils import charts, theme
from utils.db_connection import run_query

theme.hero(
    "Leaderboards",
    "Who is running the game?",
    "Most runs, highest scores, best averages, wicket-takers and more - for every format.",
)

# stat -> (column, ascending, qualifier column & minimum, label, API statsType)
STATS = {
    "Batting": {
        "Most runs": ("runs", False, None, "runs", "mostRuns"),
        "Highest score": ("highest", False, None, "HS", "highestScore"),
        "Best batting average": ("bat_avg", False, ("innings", 30), "avg", "highestAvg"),
        "Best strike rate": ("sr", False, ("innings", 30), "SR", "highestSr"),
        "Most centuries": ("centuries", False, None, "100s", "mostHundreds"),
    },
    "Bowling": {
        "Most wickets": ("wickets", False, None, "wkts", "mostWickets"),
        "Best economy": ("econ", True, ("wickets", 20), "econ", "lowestEcon"),
        "Best bowling average": ("bowl_avg", True, ("wickets", 20), "avg", "lowestAvg"),
    },
    "Fielding": {"Most dismissals": ("dismissals", False, None, "dis.", "")},
}


@st.cache_data(ttl=300, show_spinner=False)
def db_stats(fmt: str) -> pd.DataFrame:
    return run_query(
        "SELECT p.full_name, p.country, p.playing_role, SUM(c.matches) AS matches, SUM(c.innings) AS innings, "
        "SUM(c.total_runs) AS runs, MAX(c.highest_score) AS highest, SUM(c.centuries) AS centuries, "
        "SUM(c.total_wickets) AS wickets, SUM(c.catches + c.stumpings) AS dismissals, "
        "SUM(c.total_runs) * 1.0 / NULLIF(SUM(c.innings - c.not_outs), 0) AS bat_avg, "
        "AVG(c.strike_rate) AS sr, AVG(c.economy_rate) AS econ, AVG(c.bowling_average) AS bowl_avg "
        "FROM player_career_stats c JOIN players p ON p.player_id = c.player_id "
        "WHERE :f = 'All' OR c.match_format = :f GROUP BY p.player_id, p.full_name, p.country, p.playing_role",
        {"f": fmt},
    )


c1, c2, c3, c4 = st.columns([1.2, 1.3, 1.5, 1.2])
fmt = c1.segmented_control("Format", ["All", "Test", "ODI", "T20I"], default="All") or "All"
cat = c2.segmented_control("Category", list(STATS), default="Batting") or "Batting"
stat = c3.selectbox("Statistic", list(STATS[cat]))
use_api = c4.toggle(
    "Use Cricbuzz API",
    value=live_service.api_status()["configured"],
    disabled=not live_service.api_status()["configured"],
    help="Needs RAPIDAPI_KEY. Otherwise the leaderboard is computed from SQL.",
)
col, asc, qual, unit, api_type = STATS[cat][stat]

df, source = pd.DataFrame(), "SQL database"
if use_api and api_type and not st.session_state.get("force_demo"):
    try:
        df = live_service.api_top_stats(api_type, {"Test": 1, "ODI": 2, "T20I": 3}.get(fmt))
        source = "Cricbuzz API"
    except CricbuzzAPIError as exc:
        theme.callout(
            f"API unavailable ({theme.esc(str(exc))}). Showing SQL-computed leaderboard.", "warn"
        )

board = pd.DataFrame()
if source == "Cricbuzz API":
    board = build_api_board(df, asc)
    if board.empty:  # never label SQL numbers as API data
        theme.callout(
            "The API returned no usable table for this selection. Showing the SQL-computed leaderboard.",
            "warn",
        )
        source = "SQL database"
if source != "Cricbuzz API":
    raw = db_stats(fmt)
    if qual:
        raw = raw[raw[qual[0]] >= qual[1]]
    raw = raw.dropna(subset=[col]).sort_values(col, ascending=asc).reset_index(drop=True)
    board = raw.assign(
        name=raw.full_name,
        value=raw[col],
        sub=raw.country + " | " + raw.matches.astype(int).astype(str) + " matches",
    )

theme.render(
    f'<span class="cb-pill {"teal" if source == "Cricbuzz API" else "gold"}">Source: {source}</span> '
    f'<span class="cb-pill">{fmt} &middot; {stat}</span>'
)
if board.empty:
    st.warning("No data for this selection.")
    st.stop()

top = board.head(10)
fmtv = (
    (lambda v: f"{v:,.0f}")
    if col in ("runs", "highest", "centuries", "wickets", "dismissals")
    else (lambda v: f"{v:,.2f}")
)
theme.podium([(r["name"], fmtv(r["value"]), r["sub"]) for r in top.head(3).to_dict("records")])
tab_a, tab_b, tab_c = st.tabs(["Leaderboard", "Chart", "Full table"])
with tab_a:
    peak = max(float(top["value"].abs().max()), 1e-9)
    ratio = (lambda v: (peak - v + peak * 0.1) / peak / 1.1) if asc else (lambda v: v / peak)
    theme.leaderboard(
        [(r["name"], r["sub"], ratio(r["value"]), fmtv(r["value"])) for r in top.to_dict("records")]
    )
with tab_b:
    st.plotly_chart(charts.bar_h(top, "value", "name", f"{stat} ({unit})"), width="stretch")

    if "country" in board:
        by_country = (
            board.head(25)
            .groupby("country")
            .size()
            .reset_index(name="players")
            .sort_values("players", ascending=False)
        )

        fig = charts.donut(
            by_country["country"],
            by_country["players"],
            "Top 25 by Country",
        )

        fig.update_layout(
            height=420,
            margin=dict(t=70, b=30, l=20, r=20),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.12,
                xanchor="center",
                x=0.5,
                font=dict(size=10),
            ),
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent",
            hovertemplate=(
                "<b>%{label}</b><br>"
                "Players: %{value}<br>"
                "Share: %{percent}<extra></extra>"
            ),
        )

        st.plotly_chart(fig, width="stretch")

with tab_c:
    st.dataframe(
        board.drop(columns=["sub"], errors="ignore"), width="stretch", hide_index=True, height=480
    )
    st.download_button(
        "Download CSV",
        board.to_csv(index=False),
        f"top_{stat.lower().replace(' ', '_')}.csv",
        "text/csv",
    )