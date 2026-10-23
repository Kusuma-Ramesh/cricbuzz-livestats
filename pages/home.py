"""Home: project overview, headline numbers, spotlight players and navigation."""

from datetime import date

import streamlit as st

from services import analytics
from utils import theme
from utils.db_connection import run_query

theme.hero(
    "Sports analytics platform",
    "Cricket intelligence, rebuilt from the data up.",
    "Live Cricbuzz scores, a normalised SQL warehouse, 25 analytical queries and a full CRUD "
    "studio - in one cinematic, fast dashboard.",
    [
        ("Python", "teal"),
        ("Streamlit", "teal"),
        ("SQL", "gold"),
        ("REST API", "gold"),
        ("pandas", "mag"),
    ],
)

k = analytics.kpis()
theme.kpi_row(
    [
        ("Matches", f"{k['matches']:,}", f"across {k['series']} series", "#14B8A6"),
        ("Players", f"{k['players']:,}", "in 10 national squads", "#E8A33D"),
        ("Runs scored", f"{k['runs']:,}", f"{k['centuries']:,} centuries", "#E879F9"),
        ("Wickets", f"{k['wickets']:,}", f"{k['sixes']:,} sixes hit", "#60A5FA"),
    ]
)

# ---- insight of the day (deterministic per day)
insights = []
toss = run_query(
    "SELECT SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS p "
    "FROM matches WHERE winner_id IS NOT NULL"
)
insights.append(
    f"Toss winners go on to win <b>{toss.p.iloc[0]:.1f}%</b> of matches in this dataset."
)
top = analytics.player_ratings().head(1)
if not top.empty:
    t = top.iloc[0]
    insights.append(
        f"<b>{theme.esc(t.full_name)}</b> ({theme.esc(t.country)}) leads the overall "
        f"player ratings with an OVR of <b>{int(t.OVR)}</b>."
    )
best = analytics.team_table().assign(rate=lambda d: d.won / d.played).sort_values("rate").iloc[-1]
insights.append(
    f"<b>{theme.esc(best.team_name)}</b> has the best win rate at "
    f"<b>{best.rate * 100:.1f}%</b> from {int(best.played)} matches."
)
theme.callout("Insight of the day &middot; " + insights[date.today().toordinal() % len(insights)])

# ---- spotlight
theme.section(
    "Player spotlight", "FIFA-style ratings built from the weighted formula in SQL question 21"
)
ratings = analytics.player_ratings().head(5)
cols = st.columns(5)
for i, (col, row) in enumerate(zip(cols, ratings.to_dict("records"))):
    col.markdown(theme.player_card(row, i * 90), unsafe_allow_html=True)

# ---- results + form
left, right = st.columns([1.15, 1])
with left:
    theme.section("Latest results", "from the matches table")
    rows = ""
    for r in analytics.recent_results(7).itertuples():
        unit = "runs" if r.victory_type == "runs" else "wkts"
        rows += (
            f'<div class="cb-lb"><span class="n">{theme.esc(r.match_format)}</span>'
            f'<div class="nm">{theme.esc(r.t1)} v {theme.esc(r.t2)}'
            f"<small>{theme.esc(r.venue_name)} &middot; {theme.esc(r.match_date)}</small></div>"
            f'<span class="cb-pill teal">{theme.esc(r.winner)} by {int(r.victory_margin)} {unit}</span></div>'
        )
    theme.render(f'<div class="cb-card" style="padding:8px">{rows}</div>')
with right:
    theme.section("Team form", "last six completed matches")
    form = analytics.team_form()
    table = analytics.team_table().head(6)
    rows = ""

    for r in table.itertuples():
        rate = (r.won / r.played * 100) if r.played else 0

        rows += (
            f'<div class="cb-lb"><div class="nm">{theme.esc(r.team_name)}'
            f"<small>{r.won}/{r.played} won</small></div>{theme.form_pills(form.get(r.short_name, []))}"
            f'<span class="v">{rate:.0f}%</span></div>'
        )
    theme.render(f'<div class="cb-card" style="padding:8px">{rows}</div>')

# ---- navigation cards
theme.section("Explore the platform", "five modules, one connected data model")
cards = [
    (
        "pages/live_matches.py",
        "Live Matches",
        "Real-time scorecards, batting and bowling cards, venue and status.",
        "sensors",
    ),
    (
        "pages/top_players.py",
        "Top Player Stats",
        "Podiums and leaderboards for runs, wickets, averages and more.",
        "leaderboard",
    ),
    (
        "pages/sql_analytics.py",
        "SQL Analytics",
        "25 questions with explanations, results, charts and a safe SQL console.",
        "database",
    ),
    (
        "pages/crud_studio.py",
        "CRUD Studio",
        "Create, update and delete players, matches, batting and bowling rows.",
        "edit_note",
    ),
    (
        "pages/player_duel.py",
        "Player Duel",
        "Head-to-head radar, form strip and cards for any two players.",
        "compare_arrows",
    ),
]
cols = st.columns(5)
for col, (path, title, desc, icon) in zip(cols, cards):
    with col:
        theme.render(
            f'<div class="cb-card" style="min-height:130px"><b>{title}</b>'
            f'<p style="color:var(--ink-2);font-size:12.5px;margin:6px 0 0">{desc}</p></div>'
        )
        st.page_link(path, label=f"Open {title}", icon=f":material/{icon}:")

# ---- architecture + docs
theme.section("How it fits together", "clean layers; each one only talks to the next")
flow = [
    "Cricbuzz API",
    "api/ client + parsers",
    "services/ logic",
    "utils/db_connection",
    "SQLite database",
    "Streamlit pages",
]
theme.render(
    '<div class="cb-card" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">'
    + '<span style="color:var(--accent)">&rarr;</span>'.join(
        f'<span class="cb-pill teal">{f}</span>' for f in flow
    )
    + "</div>"
)
with st.expander("Project folder structure & documentation"):
    st.code(
        "cricbuzz_livestats/\n"
        "|-- main.py              # router + shared HUD, ticker, sidebar\n"
        "|-- pages/               # home, live_matches, top_players, sql_analytics, crud_studio, ...\n"
        "|-- api/                 # Cricbuzz client (retry, rate-limit aware) + JSON parsers\n"
        "|-- services/            # analytics, crud, live_service (business logic)\n"
        "|-- utils/               # config, db_connection, queries (25 SQL), theme, charts, overs\n"
        "|-- database/            # models (schema) + synthetic seed generator\n"
        "|-- sql/                 # schema.sql, queries.sql (exported)\n"
        "|-- scripts/             # seed_database.py, export_sql.py, sync_from_api.py\n"
        "|-- tests/               # pytest suite\n"
        "`-- docs/                # architecture notes",
        language="text",
    )
    st.caption("Full setup, API-key and database instructions are in README.md and docs/.")
