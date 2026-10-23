"""SQL Analytics: the 25 questions, an insight dashboard and a read-only SQL console."""

import pandas as pd
import streamlit as st
from sqlalchemy import inspect

from services import analytics
from utils import charts, overs, theme
from utils.db_connection import DatabaseError, get_engine, run_query, run_readonly
from utils.queries import BY_NUMBER, LEVELS, Q, default_params

theme.hero(
    "SQL lab",
    "25 questions. One data model. Zero guesswork.",
    "Pick a question, read the business problem, study the SQL, run it and see the result.",
    [("Beginner 1-8", "teal"), ("Intermediate 9-16", "gold"), ("Advanced 17-25", "mag")],
)

if "understood" not in st.session_state:
    st.session_state.understood = set()


def prettify(df: pd.DataFrame) -> pd.DataFrame:
    """Show stored legal balls in cricket notation (4.3) next to the raw count."""
    if "total_balls" in df.columns:
        df = df.copy()
        df.insert(
            df.columns.get_loc("total_balls"),
            "total_overs",
            df["total_balls"].map(overs.to_notation),
        )
    return df


def paginated(df: pd.DataFrame, key: str) -> None:
    size = st.select_slider("Rows per page", [25, 50, 100, 250], value=50, key=f"{key}_size")
    pages = max(1, -(-len(df) // size))
    page = st.number_input("Page", 1, pages, 1, key=f"{key}_page") if pages > 1 else 1
    lo = (page - 1) * size
    st.dataframe(df.iloc[lo : lo + size], width="stretch", hide_index=True)
    st.caption(f"Rows {lo + 1 if len(df) else 0}-{min(lo + size, len(df))} of {len(df):,}")


tab_q, tab_i, tab_c = st.tabs(["Question explorer", "Insight dashboard", "SQL console"])

with tab_q:
    left, right = st.columns([1, 2.6])
    with left:
        level = st.segmented_control("Level", ["All"] + LEVELS, default="All") or "All"
        pool = [q for q in Q if level in ("All", q.level)]
        qn = st.radio(
            "Question",
            [q.number for q in pool],
            label_visibility="collapsed",
            format_func=lambda n: (
                f"{'✓ ' if n in st.session_state.understood else ''}Q{n:02d}  {BY_NUMBER[n].title}"
            ),
        )
        done = len(st.session_state.understood)
        st.progress(done / 25, text=f"{done} / 25 understood")
    q = BY_NUMBER[qn]
    with right:
        tone = {"Beginner": "teal", "Intermediate": "gold", "Advanced": "mag"}[q.level]
        chips = "".join(f'<span class="cb-pill">{theme.esc(c)}</span> ' for c in q.concepts)
        tabs_used = "".join(f'<span class="cb-pill teal">{theme.esc(t)}</span> ' for t in q.tables)
        theme.render(
            f'<div class="cb-card"><span class="cb-pill {tone}">{q.level}</span> '
            f'<h3 style="margin:10px 0 4px">Q{q.number:02d} &middot; {theme.esc(q.title)}</h3>'
            f'<p style="color:var(--ink-2);margin:0 0 10px">{theme.esc(q.business)}</p>'
            f'<div class="cb-kicker" style="margin-bottom:4px">SQL concepts</div>{chips}'
            f'<div class="cb-kicker" style="margin:10px 0 4px">Tables</div>{tabs_used}</div>'
        )
        st.code(q.sql, language="sql")
        try:
            df = prettify(run_query(q.sql, default_params()))
            ms = None
        except DatabaseError as exc:
            st.error(f"Query failed: {exc}")
            df = pd.DataFrame()
        theme.kpi_row(
            [
                ("Rows", f"{len(df):,}", "returned", "#14B8A6"),
                ("Columns", str(len(df.columns)), "in result", "#E8A33D"),
                ("Level", q.level, f"question {q.number} of 25", "#E879F9"),
            ],
            cols=3,
        )
        if q.tip:
            theme.callout(f"<b>Optimisation note.</b> {theme.esc(q.tip)}")
        if not df.empty:
            fig = charts.auto_chart(df, q.chart)
            if fig is not None:
                st.plotly_chart(fig, width="stretch")
            paginated(df, f"q{qn}")
            st.download_button(
                "Download full result (CSV)", df.to_csv(index=False), f"q{qn:02d}.csv", "text/csv"
            )
        elif not df.shape[1]:
            st.info("No rows returned.")
        mark = st.checkbox(
            "I understand this query", value=qn in st.session_state.understood, key=f"u{qn}"
        )
        (st.session_state.understood.add if mark else st.session_state.understood.discard)(qn)

with tab_i:
    k = analytics.kpis()
    c1, c2 = st.columns([1.6, 1])
    ry = analytics.runs_by_format_year()
    c1.plotly_chart(
        charts.lines(ry, "year", "runs_per_match", "format", "Runs per match, by year"),
        width="stretch",
    )
    fs = analytics.format_split()
    c2.plotly_chart(
        charts.donut(fs.format, fs.matches, "Match mix", f"{k['matches']:,}"), width="stretch"
    )
    c3, c4 = st.columns(2)
    hv = run_query(BY_NUMBER[12].sql)
    fig_home_away = charts.column(
        hv,
        "team_name",
        ["home_win_pct", "away_win_pct"],
        "Home vs away win %",
    )

    fig_home_away.update_layout(
        legend_title_text="",
        legend=dict(title_text=""),
        xaxis=dict(
            tickangle=-25,
            tickfont=dict(size=10),
        ),
    )

    fig_home_away.for_each_trace(
        lambda trace: trace.update(
            name={
                "home_win_pct": "Home wins",
                "away_win_pct": "Away wins",
            }.get(trace.name, trace.name)
        )
    )
    c3.plotly_chart(fig_home_away, width="stretch")
    heat = analytics.run_heatmap().pivot(index="position", columns="format", values="avg_runs")
    c4.plotly_chart(
        charts.heat(heat, "Average runs by batting position", fmt=".1f"), width="stretch"
    )

    vs = analytics.venue_scoring().head(12).copy()
    vs["avg_innings_total"] = vs["avg_innings_total"].round(1)

    fig_venues = charts.bar_h(
        vs,
        "avg_innings_total",
        "venue_name",
        "Highest-scoring ODI venues (average innings total)",
        height=430,
    )


    # Venue name and total are read directly from the bar's own data (y and x).
    fig_venues.update_traces(
        texttemplate="%{x:.1f}",
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Average innings total: %{x:.1f}<extra></extra>",
    )
    st.plotly_chart(fig_venues, width="stretch")


with tab_c:
    theme.callout(
        "The console accepts a <b>single SELECT</b> statement and runs on a read-only connection. "
        "Named parameters <code>:today</code>, <code>:d30</code> and <code>:d3y</code> are available."
    )
    examples = {
        "Top 10 ODI run scorers": BY_NUMBER[3].sql,
        "Matches per venue": "SELECT v.venue_name, COUNT(*) AS matches\nFROM matches m JOIN venues v ON v.venue_id = m.venue_id\nGROUP BY v.venue_name\nORDER BY matches DESC",
        "Sixes per team": "SELECT t.team_name, SUM(b.sixes) AS sixes\nFROM batting_performances b JOIN teams t ON t.team_id = b.team_id\nGROUP BY t.team_name\nORDER BY sixes DESC",
    }
    pick = st.selectbox("Start from an example", list(examples))
    sql = st.text_area("SQL", examples[pick], height=190, key=f"console_{pick}")
    run = st.button("Run query", type="primary", icon=":material/play_arrow:")
    with st.expander("Schema reference"):
        insp = inspect(get_engine())
        for t in insp.get_table_names():
            st.markdown(f"**{t}** - " + ", ".join(c["name"] for c in insp.get_columns(t)))
    if run:
        try:
            res, ms = run_readonly(sql, default_params())
            theme.render(
                f'<span class="cb-pill teal">{len(res):,} rows</span> <span class="cb-pill gold">{ms:.1f} ms</span>'
            )
            paginated(prettify(res), "console")
            st.download_button("Download CSV", res.to_csv(index=False), "console.csv", "text/csv")
        except DatabaseError as exc:
            st.error(str(exc))