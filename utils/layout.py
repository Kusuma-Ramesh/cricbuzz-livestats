"""Shared page chrome: database bootstrap, HUD, live ticker and sidebar controls."""

from __future__ import annotations

import streamlit as st

from services import analytics, live_service
from utils import theme
from utils.config import settings
from utils.db_connection import DatabaseError, db_health, ensure_database


def _compact_n(n: int) -> str:
    return (
        f"{n / 1_000_000:.1f}M"
        if n >= 1_000_000
        else (f"{n / 1_000:.1f}K" if n >= 10_000 else f"{n:,}")
    )


def _ticker_items() -> list[str]:
    items: list[str] = []
    live, _, _ = live_service.get_matches(
        "live", force_demo=st.session_state.get("force_demo", False)
    )
    for m in live[:4]:
        s1, s2 = m["score1"]["summary"], m["score2"]["summary"]
        items.append(
            f'<span class="cb-live">LIVE</span> <b>{theme.esc(m["team1_short"])}</b> {theme.esc(s1)} v <b>{theme.esc(m["team2_short"])}</b> {theme.esc(s2)}'
        )
    for r in analytics.recent_results(8).itertuples():
        unit = "runs" if r.victory_type == "runs" else "wkts"
        items.append(
            f"<b>{theme.esc(r.winner)}</b> beat {theme.esc(r.t2 if r.winner == r.t1 else r.t1)} by <em>{int(r.victory_margin)} {unit}</em> &middot; {theme.esc(r.match_format)}"
        )
    return items


def sidebar() -> None:
    with st.sidebar:
        st.markdown("---")
        st.toggle(
            "Force demo feed",
            key="force_demo",
            help="Skip the Cricbuzz API and use the simulated live feed.",
        )
        h = db_health()
        theme.render(
            f'<div class="cb-callout" style="font-size:12px"><b>Database</b> &middot; {theme.esc(h["dialect"]).upper()}<br>{h.get("matches", 0):,} matches &middot; {h.get("players", 0):,} players</div>'
        )
        with st.expander("Maintenance"):
            st.caption("Rebuild the schema and regenerate the fictional demo dataset.")
            sure = st.checkbox("I understand this erases current data")
            if st.button("Re-seed demo data", disabled=not sure, width="stretch"):
                with st.spinner("Re-seeding..."):
                    ensure_database(force=True)
                    st.cache_data.clear()
                st.rerun()
        st.caption(f"v1.0 · {settings.app_name}")


def boot() -> None:
    """Run once per rerun, before the active page renders."""
    try:
        with st.spinner("Preparing database..."):
            ensure_database()
    except DatabaseError as exc:
        st.error(f"Database connection failed: {exc}")
        st.info("Check DATABASE_URL in your .env file (see README). SQLite works out of the box.")
        st.stop()
    k = analytics.kpis()
    api = live_service.api_status()
    live_mode = api["configured"] and not st.session_state.get("force_demo", False)
    theme.hud(
        [
            ("Matches", _compact_n(k["matches"]), ""),
            ("Players", _compact_n(k["players"]), ""),
            ("Runs", _compact_n(k["runs"]), "gold"),
            ("Wickets", _compact_n(k["wickets"]), "teal"),
        ],
        [
            ("LIVE API" if live_mode else "DEMO FEED", "teal" if live_mode else "gold"),
            ("SQL READY", "teal"),
        ],
    )
    theme.ticker(_ticker_items())
    sidebar()
