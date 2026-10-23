"""Live Matches: match centre, scorecards, worm chart and historical edge from the SQL database."""

import streamlit as st

from api.parsers import empty_scorecard_message, innings_totals
from services import live_service
from utils import charts, theme
from utils.db_connection import run_query
import pandas as pd
theme.hero(
    "Match centre",
    "Every ball, as it happens.",
    "Live, recent and upcoming internationals from the Cricbuzz API. Without an API key the page "
    "runs on a clearly labelled demo feed built from the local database.",
)

c1, c2, c3 = st.columns([2, 1, 1.4])
kind = (
    c1.segmented_control(
        "Feed",
        ["live", "recent", "upcoming"],
        default="live",
        format_func=str.title,
        key="feed_kind",
    )
    or "live"
)
auto = c2.toggle("Auto-refresh (30s)", value=False)
if c3.button("Refresh now", icon=":material/refresh:"):
    st.cache_data.clear()
    st.rerun()
if "requested_match" not in st.session_state:
    st.session_state["requested_match"] = None

@st.fragment(run_every=30 if auto else None)
def match_centre() -> None:
    matches, source, note = live_service.get_matches(
        kind, st.session_state.get("force_demo", False)
    )
    if note:
        theme.callout(theme.esc(note), "warn")
    if not matches:
        st.info("No matches in this feed right now.")
        return
    theme.render(
        f'<span class="cb-pill {"teal" if source == "api" else "gold"}">'
        f"Source: {'Cricbuzz API' if source == 'api' else 'Demo feed'}</span>"
    )

    labels = {
        f"{m['team1_short']} vs {m['team2_short']} - {m['format']} {m['desc']}": m
        for m in matches
    }

    for start in range(0, len(matches), 3):
        cols = st.columns(3)
        for col, m in zip(cols, matches[start: start + 3]):
            label = next(key for key, value in labels.items() if value is m)
            with col:
                st.markdown(
                    theme.match_card(m, (start % 3) * 80),
                    unsafe_allow_html=True,
                )

                if st.button(
                        "View scorecard",
                        key=f"select_match_{m['match_id']}",
                        use_container_width=True,
                ):
                    st.session_state["requested_match"] = label
                    st.rerun()

    options = list(labels)

    requested = st.session_state.get("requested_match")
    if requested not in options:
        requested = options[0]

    if st.session_state.get("live_match_selector") not in options:
        st.session_state["live_match_selector"] = requested

    if st.session_state.get("requested_match") in options:
        st.session_state["live_match_selector"] = requested
        st.session_state["requested_match"] = None

    choice = st.selectbox(
        "Match",
        options,
        label_visibility="collapsed",
        key="live_match_selector",
    )

    m = labels[choice]

    innings, card_note = live_service.get_scorecard(m, source)
    if card_note:
        theme.callout(theme.esc(card_note), "warn")

    left, right = st.columns([2.2, 1])
    with right:
        theme.render(
            f'<div class="cb-card"><div class="cb-kicker">Venue</div><h3 style="margin:6px 0">'
            f'{theme.esc(m["venue"] or "TBC")}</h3><p style="color:var(--ink-2);margin:0">'
            f'{theme.esc(m["city"])}</p><div class="cb-status">{theme.esc(m["status"])}</div></div>'
        )
        # historical edge computed with SQL from the local database

        h = run_query(
            "SELECT "
            "SUM(CASE WHEN m.winner_id = t1.team_id THEN 1 ELSE 0 END) AS wa, "
            "COUNT(*) AS n "
            "FROM matches m "
            "JOIN teams t1 ON t1.team_id = m.team1_id "
            "JOIN teams t2 ON t2.team_id = m.team2_id "
            "WHERE ((t1.team_name = :a AND t2.team_name = :b) "
            "OR (t1.team_name = :b AND t2.team_name = :a)) "
            "AND m.winner_id IN (t1.team_id, t2.team_id)",
            {"a": m["team1"], "b": m["team2"]},
        )

        if not h.empty and pd.notna(h.n.iloc[0]) and int(h.n.iloc[0]) > 0:
            pa = float(h.wa.iloc[0] or 0) / int(h.n.iloc[0]) * 100
            st.caption(
                f"Historical head-to-head in the database "
                f"({int(h.n.iloc[0])} completed matches)"
            )
            st.plotly_chart(
                charts.win_bar(m["team1_short"], m["team2_short"], pa),
                width="stretch",
            )

    with left:
        if not innings:
            level, text = empty_scorecard_message(m)
            (st.warning if level == "warning" else st.info)(text)
            totals = innings_totals(m)
            if totals:
                st.caption(f"Innings totals from the {'Cricbuzz API' if source == 'api' else 'demo'} feed")
                st.dataframe(pd.DataFrame(totals), hide_index=True, width="stretch")
        else:
            tabs = st.tabs([f"{i['team']} {i['runs']}/{i['wkts']}" for i in innings])
            for tab, inn in zip(tabs, innings):
                with tab:
                    st.dataframe(
                        inn["batting"],
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "SR": st.column_config.ProgressColumn(
                                "SR", min_value=0, max_value=250, format="%.1f"
                            ),
                            "R": st.column_config.NumberColumn("R", format="%d"),
                        },
                    )
                    st.dataframe(inn["bowling"], hide_index=True, width="stretch")
    if source == "demo" and m["state"] != "Upcoming":
        worm = live_service.worm_series(m)
        if not worm.empty:
            st.plotly_chart(charts.worm(worm), width="stretch")
            st.caption("Run progression is simulated in demo mode.")


match_centre()