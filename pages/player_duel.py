"""Player Duel: head-to-head comparison with ratings cards, radar, format table and form strip."""

import streamlit as st

from services import analytics
from utils import charts, theme

theme.hero(
    "Head to head",
    "Pick two players. Settle the argument.",
    "Ratings, radar, per-format numbers and recent form - computed live from SQL.",
)

ratings = analytics.player_ratings()
names = ratings.set_index("player_id").full_name.to_dict()
ids = list(names)
c1, c2 = st.columns(2)
a = c1.selectbox("Player A", ids, index=0, format_func=names.get)
b = c2.selectbox("Player B", ids, index=min(1, len(ids) - 1), format_func=names.get)
if a == b:
    st.warning("Choose two different players.")
    st.stop()

ra = ratings[ratings.player_id == a].iloc[0].to_dict()
rb = ratings[ratings.player_id == b].iloc[0].to_dict()
col_a, col_mid, col_b = st.columns([1, 1.7, 1])
col_a.markdown(theme.player_card(ra), unsafe_allow_html=True)
col_b.markdown(theme.player_card(rb, 100), unsafe_allow_html=True)


def radar_values(r: dict) -> list[float]:
    pool = ratings
    pct = lambda col, v, inv=False: float(
        (pool[col] <= v).mean() * 100 if not inv else (pool[col] >= v).mean() * 100
    )  # noqa: E731
    return [
        pct("runs", r["runs"]),
        pct("bat_avg", r["bat_avg"] or 0),
        pct("strike_rate", r["strike_rate"] or 0),
        pct("wickets", r["wickets"]),
        pct("economy", r["economy"] or pool.economy.max(), inv=True),
        pct("catches", r["catches"] + 2 * r["stumpings"]),
    ]


with col_mid:
    st.plotly_chart(
        charts.radar(
            ["Runs", "Average", "Strike rate", "Wickets", "Economy", "Fielding"],
            {names[a]: radar_values(ra), names[b]: radar_values(rb)},
        ),
        width="stretch",
    )
edge = ra["OVR"] - rb["OVR"]
winner = names[a] if edge > 0 else names[b] if edge < 0 else None
theme.callout(
    f"<b>Verdict.</b> {'Dead heat on overall rating.' if winner is None else f'{theme.esc(winner)} has the edge by {abs(int(edge))} rating points.'}"
)

theme.section("Career by format")
pa, pb = analytics.player_profile(a), analytics.player_profile(b)
cols = [
    "match_format",
    "matches",
    "total_runs",
    "batting_average",
    "strike_rate",
    "centuries",
    "total_wickets",
    "economy_rate",
]
x, y = st.columns(2)
x.markdown(f"**{names[a]}**")
x.dataframe(pa["stats"][cols], hide_index=True, width="stretch")
y.markdown(f"**{names[b]}**")
y.dataframe(pb["stats"][cols], hide_index=True, width="stretch")

theme.section("Recent form", "last 15 innings - gold = century, teal = fifty")
f1, f2 = st.columns(2)
for col, prof, nm in ((f1, pa, names[a]), (f2, pb, names[b])):
    if not prof["last"].empty:
        col.plotly_chart(charts.innings_bars(prof["last"], nm), width="stretch")
