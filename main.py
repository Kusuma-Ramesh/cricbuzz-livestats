"""Cricbuzz LiveStats - application entry point.

Run with:  streamlit run main.py
This file is the router: it applies the theme, bootstraps the database, draws the shared
HUD / ticker / sidebar and then hands control to the selected page in pages/.
"""

import streamlit as st

st.set_page_config(
    page_title="Cricbuzz LiveStats", page_icon="🏏", layout="wide", initial_sidebar_state="expanded"
)

from utils import layout, theme  # noqa: E402  (must come after set_page_config)

theme.inject_theme()
layout.boot()

PAGES = [
    st.Page("pages/home.py", title="Home", icon=":material/stadium:", default=True),
    st.Page("pages/live_matches.py", title="Live Matches", icon=":material/sensors:"),
    st.Page("pages/top_players.py", title="Top Player Stats", icon=":material/leaderboard:"),
    st.Page("pages/sql_analytics.py", title="SQL Analytics", icon=":material/database:"),
    st.Page("pages/crud_studio.py", title="CRUD Studio", icon=":material/edit_note:"),
    st.Page("pages/player_duel.py", title="Player Duel", icon=":material/compare_arrows:"),
    st.Page("pages/stat_arcade.py", title="Stat Arcade", icon=":material/sports_esports:"),
]
st.navigation(PAGES).run()
