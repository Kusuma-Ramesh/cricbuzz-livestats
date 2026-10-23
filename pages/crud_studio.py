"""CRUD Studio: one page, four entities (Players, Matches, Batting, Bowling)."""

from datetime import date

import pandas as pd
import streamlit as st

from services import crud
from utils import theme
from utils.db_connection import DatabaseError, run_query

theme.hero(
    "Data studio",
    "Create. Read. Update. Delete.",
    "Form-based management with validation, transactions and a full audit trail.",
)


def attempt(fn, ok: str) -> bool:
    """Run a write; show friendly errors; clear caches on success."""
    try:
        fn()
    except crud.ValidationError as exc:
        st.warning(str(exc))
    except DatabaseError as exc:
        st.error(f"Database error: {exc}")
    else:
        st.cache_data.clear()
        st.toast(ok, icon="✅")
        st.success(ok)
        return True
    return False


def players_df() -> pd.DataFrame:
    return run_query("SELECT player_id, full_name, country FROM players ORDER BY full_name")


def pick(label: str, df: pd.DataFrame, id_col: str, fmt, key: str):
    ids = df[id_col].tolist()
    if not ids:
        st.info("Nothing to select.")
        return None
    return st.selectbox(label, ids, format_func=lambda i: fmt(df[df[id_col] == i].iloc[0]), key=key)


def player_form(prefix: str, row: dict | None = None):
    row = row or {}
    countries = run_query("SELECT DISTINCT country FROM players ORDER BY country").country.tolist()
    with st.form(f"{prefix}_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Full name", row.get("full_name", ""))
        country = c2.selectbox(
            "Country",
            countries,
            index=countries.index(row["country"]) if row.get("country") in countries else 0,
        )
        c3, c4, c5 = st.columns(3)
        role = c3.selectbox(
            "Playing role",
            crud.ROLES,
            index=crud.ROLES.index(row["playing_role"])
            if row.get("playing_role") in crud.ROLES
            else 0,
        )
        bat = c4.selectbox(
            "Batting style",
            crud.BAT_STYLES,
            index=crud.BAT_STYLES.index(row["batting_style"])
            if row.get("batting_style") in crud.BAT_STYLES
            else 0,
        )
        bowl_default = row.get("bowling_style") or "Does not bowl"
        bowl = c5.selectbox(
            "Bowling style",
            crud.BOWL_STYLES,
            index=crud.BOWL_STYLES.index(bowl_default) if bowl_default in crud.BOWL_STYLES else 0,
        )
        dob_val = (
            pd.to_datetime(row["date_of_birth"]).date()
            if row.get("date_of_birth")
            else date(1998, 1, 1)
        )
        dob = st.date_input(
            "Date of birth", dob_val, min_value=date(1960, 1, 1), max_value=date.today()
        )
        submit = st.form_submit_button("Save", type="primary")
    data = dict(
        full_name=name,
        country=country,
        playing_role=role,
        batting_style=bat,
        bowling_style=bowl,
        date_of_birth=dob,
    )
    return submit, data


entity = (
    st.segmented_control("Entity", ["Players", "Matches", "Batting", "Bowling"], default="Players")
    or "Players"
)
t_create, t_read, t_update, t_delete = st.tabs(["Create", "Browse", "Update", "Delete"])

# =============================================================== PLAYERS
if entity == "Players":
    with t_create:
        submit, data = player_form("pc")
        if submit:
            attempt(lambda: crud.create_player(data), "Player created.")
    with t_read:
        c1, c2, c3 = st.columns(3)
        s = c1.text_input("Search name")
        cty = c2.selectbox(
            "Country",
            ["All"]
            + run_query("SELECT DISTINCT country FROM players ORDER BY country").country.tolist(),
        )
        rl = c3.selectbox("Role", ["All"] + crud.ROLES)
        df = crud.list_players(s, cty, rl)
        st.dataframe(df, width="stretch", hide_index=True)
        st.caption(f"{len(df):,} players shown (newest first, max 500)")
    with t_update:
        s = st.text_input("Find player to edit", key="pu_s")
        lst = crud.list_players(s, limit=100)
        pid = pick(
            "Player",
            lst,
            "player_id",
            lambda r: f"#{r.player_id} {r.full_name} ({r.country})",
            "pu_pick",
        )
        if pid:
            submit, data = player_form(f"pu{pid}", lst[lst.player_id == pid].iloc[0].to_dict())
            if submit:
                attempt(lambda: crud.update_player(pid, data), "Player updated.")
    with t_delete:
        s = st.text_input("Find player to delete", key="pd_s")
        lst = crud.list_players(s, limit=100)
        pid = pick(
            "Player",
            lst,
            "player_id",
            lambda r: f"#{r.player_id} {r.full_name} ({r.country})",
            "pd_pick",
        )
        if pid:
            usage = crud.player_usage(pid)
            st.caption(
                f"Linked rows - batting: {usage['batting']}, bowling: {usage['bowling']}, fielding: {usage['fielding']}"
            )
            cascade = st.checkbox("Also delete this player's performances and career stats")
            confirm = st.text_input("Type DELETE to confirm")
            if st.button("Delete player", type="primary", disabled=confirm != "DELETE"):
                attempt(lambda: crud.delete_player(pid, cascade), "Player deleted.")

# =============================================================== MATCHES
elif entity == "Matches":
    lk = crud.lookups()
    teams, venues, series = lk["teams"], lk["venues"], lk["series"]
    tname = dict(zip(teams.team_id, teams.team_name))
    with t_create:
        with st.form("mc"):
            c1, c2, c3 = st.columns(3)
            fmt = c1.selectbox("Format", ["Test", "ODI", "T20I"])
            t1 = c2.selectbox("Team 1", teams.team_id, format_func=tname.get)
            t2 = c3.selectbox("Team 2", teams.team_id, index=1, format_func=tname.get)
            c4, c5, c6 = st.columns(3)
            ser = c4.selectbox(
                "Series",
                series.series_id,
                format_func=dict(zip(series.series_id, series.series_name)).get,
            )
            ven = c5.selectbox(
                "Venue",
                venues.venue_id,
                format_func=dict(zip(venues.venue_id, venues.venue_name)).get,
            )
            when = c6.date_input("Match date", date.today(), max_value=date.today())
            c7, c8 = st.columns(2)
            toss = c7.selectbox(
                "Toss winner", [None, t1, t2], format_func=lambda x: "-" if x is None else tname[x]
            )
            dec = c8.selectbox(
                "Toss decision",
                [None, "bat", "bowl"],
                format_func=lambda x: "-" if x is None else x,
            )
            c9, c10, c11 = st.columns(3)
            win = c9.selectbox(
                "Winner",
                [None, t1, t2],
                format_func=lambda x: "No result" if x is None else tname[x],
            )
            vt = c10.selectbox("Victory type", ["runs", "wickets"])
            vm = c11.number_input("Margin", 0, 600, 0)
            desc = st.text_input(
                "Description", f"{tname[t1][:3].upper()} vs {tname[t2][:3].upper()}, {fmt}"
            )
            go = st.form_submit_button("Create match", type="primary")
        if go:
            attempt(
                lambda: crud.create_match(
                    dict(
                        series_id=ser,
                        description=desc,
                        match_format=fmt,
                        team1_id=t1,
                        team2_id=t2,
                        venue_id=ven,
                        match_date=when,
                        toss_winner_id=toss,
                        toss_decision=dec,
                        winner_id=win,
                        victory_type=vt,
                        victory_margin=int(vm),
                    )
                ),
                "Match created.",
            )
    with t_read:
        c1, c2 = st.columns(2)
        f = c1.selectbox("Format", ["All", "Test", "ODI", "T20I"], key="mf")
        tm = c2.selectbox("Team", ["All"] + teams.team_name.tolist(), key="mt")
        st.dataframe(crud.list_matches(f, tm), width="stretch", hide_index=True)
    with t_update:
        ml = crud.list_matches(limit=200)
        mid = pick(
            "Match", ml, "match_id", lambda r: f"#{r.match_id} {r.match_date} {r.description}", "mu"
        )
        if mid:
            row = run_query(
                "SELECT team1_id, team2_id FROM matches WHERE match_id = :m", {"m": mid}
            ).iloc[0]
            opts = [None, int(row.team1_id), int(row.team2_id)]
            with st.form("mu_form"):
                w = st.selectbox(
                    "Winner", opts, format_func=lambda x: "No result" if x is None else tname[x]
                )
                c1, c2 = st.columns(2)
                vt = c1.selectbox("Victory type", ["runs", "wickets"])
                vm = c2.number_input("Margin", 0, 600, 1)
                go = st.form_submit_button("Update result", type="primary")
            if go:
                attempt(lambda: crud.update_match_result(mid, w, int(vm), vt), "Match updated.")
    with t_delete:
        ml = crud.list_matches(limit=200)
        mid = pick(
            "Match", ml, "match_id", lambda r: f"#{r.match_id} {r.match_date} {r.description}", "md"
        )
        st.caption("Deleting a match also removes its batting, bowling and fielding rows.")
        ok = st.text_input("Type DELETE to confirm", key="md_c")
        if mid and st.button("Delete match", type="primary", disabled=ok != "DELETE"):
            attempt(lambda: (crud.delete_match(mid), crud._refresh_career()), "Match deleted.")

# =============================================================== BATTING / BOWLING
else:
    batting = entity == "Batting"
    mo = crud.match_options()
    mlabel = lambda r: f"#{r.match_id} {r.match_date} {r.description}"  # noqa: E731

    def match_and_player(prefix: str):
        mid = pick("Match", mo, "match_id", mlabel, f"{prefix}_m")
        if not mid:
            return None
        m = mo[mo.match_id == mid].iloc[0]
        team = st.selectbox(
            "Team",
            [int(m.t1_id), int(m.t2_id)],
            format_func=lambda x: m.t1 if x == int(m.t1_id) else m.t2,
            key=f"{prefix}_t",
        )
        squad = run_query(
            "SELECT p.player_id, p.full_name, p.country FROM players p JOIN teams t ON t.country = p.country "
            "WHERE t.team_id = :t ORDER BY p.full_name",
            {"t": team},
        )
        pid = pick("Player", squad, "player_id", lambda r: r.full_name, f"{prefix}_p")
        return (mid, team, pid) if pid else None

    with t_create:
        ctx = match_and_player("c")
        if ctx:
            mid, team, pid = ctx
            with st.form("perf_c"):
                inn = st.number_input("Innings", 1, 4, 1)
                if batting:
                    c1, c2, c3, c4, c5 = st.columns(5)
                    pos = c1.number_input("Position", 1, 11, 1)
                    runs = c2.number_input("Runs", 0, 400, 0)
                    balls = c3.number_input("Balls", 0, 700, 0)
                    fours = c4.number_input("4s", 0, 80, 0)
                    sixes = c5.number_input("6s", 0, 40, 0)
                    out = st.checkbox("Dismissed", True)
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    ov = c1.text_input("Overs (e.g. 4.3)", "4.0")
                    mdn = c2.number_input("Maidens", 0, 20, 0)
                    rc = c3.number_input("Runs conceded", 0, 300, 0)
                    wk = c4.number_input("Wickets", 0, 10, 0)
                go = st.form_submit_button("Save", type="primary")
            if go:
                base = dict(match_id=mid, team_id=team, player_id=pid, innings_no=int(inn))
                if batting:
                    attempt(
                        lambda: crud.create_batting(
                            {
                                **base,
                                "batting_position": int(pos),
                                "runs": int(runs),
                                "balls_faced": int(balls),
                                "fours": int(fours),
                                "sixes": int(sixes),
                                "is_out": out,
                            }
                        ),
                        "Batting row created.",
                    )
                else:
                    attempt(
                        lambda: crud.create_bowling(
                            {
                                **base,
                                "overs": ov,
                                "maidens": int(mdn),
                                "runs_conceded": int(rc),
                                "wickets": int(wk),
                            }
                        ),
                        "Bowling row created.",
                    )
    with t_read:
        mf = st.selectbox(
            "Match filter",
            [None] + mo.match_id.tolist(),
            format_func=lambda x: (
                "All matches" if x is None else mlabel(mo[mo.match_id == x].iloc[0])
            ),
            key="rd_m",
        )
        s = st.text_input("Player search", key="rd_s")
        st.dataframe(
            crud.list_batting(mf, s) if batting else crud.list_bowling(mf, s),
            width="stretch",
            hide_index=True,
        )
        if not batting:
            st.caption(
                "`overs` is cricket notation (4.3 = 4 overs and 3 balls); the database stores legal balls."
            )
    with t_update:
        mf = pick("Match", mo, "match_id", mlabel, "up_m")
        rows = (
            (crud.list_batting(mf) if batting else crud.list_bowling(mf)) if mf else pd.DataFrame()
        )
        rid = (
            pick(
                "Row",
                rows,
                "perf_id",
                lambda r: f"#{r.perf_id} {r.player} (inn {r.innings_no})",
                "up_r",
            )
            if len(rows)
            else None
        )
        if rid:
            r = rows[rows.perf_id == rid].iloc[0]
            m = mo[mo.match_id == mf].iloc[0]
            full = run_query(
                f"SELECT * FROM {'batting' if batting else 'bowling'}_performances WHERE perf_id = :i",
                {"i": rid},
            ).iloc[0]
            with st.form("perf_u"):
                inn = st.number_input("Innings", 1, 4, int(r.innings_no))
                if batting:
                    c1, c2, c3, c4, c5 = st.columns(5)
                    pos = c1.number_input("Position", 1, 11, int(r.pos))
                    runs = c2.number_input("Runs", 0, 400, int(r.runs))
                    balls = c3.number_input("Balls", 0, 700, int(r.balls))
                    fours = c4.number_input("4s", 0, 80, int(r.fours))
                    sixes = c5.number_input("6s", 0, 40, int(r.sixes))
                    out = st.checkbox("Dismissed", bool(r.is_out))
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    ov = c1.text_input("Overs", r.overs)
                    mdn = c2.number_input("Maidens", 0, 20, int(r.maidens))
                    rc = c3.number_input("Runs conceded", 0, 300, int(r.runs))
                    wk = c4.number_input("Wickets", 0, 10, int(r.wickets))
                go = st.form_submit_button("Update", type="primary")
            if go:
                base = dict(
                    match_id=int(mf),
                    team_id=int(full.team_id),
                    player_id=int(full.player_id),
                    innings_no=int(inn),
                )
                if batting:
                    attempt(
                        lambda: crud.update_batting(
                            rid,
                            {
                                **base,
                                "batting_position": int(pos),
                                "runs": int(runs),
                                "balls_faced": int(balls),
                                "fours": int(fours),
                                "sixes": int(sixes),
                                "is_out": out,
                            },
                        ),
                        "Batting row updated.",
                    )
                else:
                    attempt(
                        lambda: crud.update_bowling(
                            rid,
                            {
                                **base,
                                "overs": ov,
                                "maidens": int(mdn),
                                "runs_conceded": int(rc),
                                "wickets": int(wk),
                            },
                        ),
                        "Bowling row updated.",
                    )
    with t_delete:
        mf = pick("Match", mo, "match_id", mlabel, "dl_m")
        rows = (
            (crud.list_batting(mf) if batting else crud.list_bowling(mf)) if mf else pd.DataFrame()
        )
        rid = (
            pick(
                "Row",
                rows,
                "perf_id",
                lambda r: f"#{r.perf_id} {r.player} (inn {r.innings_no})",
                "dl_r",
            )
            if len(rows)
            else None
        )
        ok = st.text_input("Type DELETE to confirm", key="dl_c")
        if rid and st.button("Delete row", type="primary", disabled=ok != "DELETE"):
            attempt(
                lambda: (crud.delete_batting if batting else crud.delete_bowling)(rid),
                "Row deleted.",
            )

with st.expander("Audit trail (last 12 changes)"):
    st.dataframe(crud.recent_audit(), width="stretch", hide_index=True)
