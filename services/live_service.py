"""Live-match data with graceful fallback.

Order of preference: real Cricbuzz API  ->  clearly-labelled demo feed built from the
local database (so the UI is fully usable without an API key or when the quota is hit).
"""

from __future__ import annotations

import hashlib
import random
import zlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from api.cricbuzz_client import CricbuzzAPIError, CricbuzzClient
from api.parsers import parse_matches, parse_scorecard
from utils.config import settings
from utils.db_connection import run_query


@st.cache_resource
def _client() -> CricbuzzClient:
    return CricbuzzClient()


def api_status() -> dict:
    c = _client()
    return {"configured": c.configured, "remaining": c.remaining}


@st.cache_data(ttl=max(settings.api_cache_seconds, 5), show_spinner=False)
def _fetch(kind: str):
    c = _client()
    payload = {"live": c.live_matches, "recent": c.recent_matches, "upcoming": c.upcoming_matches}[
        kind
    ]()
    return parse_matches(payload)


def get_matches(kind: str = "live", force_demo: bool = False) -> tuple[list[dict], str, str]:
    """Return (matches, source, message). source is 'api' or 'demo'."""
    if not force_demo and _client().configured:
        try:
            return _fetch(kind), "api", ""
        except CricbuzzAPIError as exc:
            return demo_matches(kind), "demo", f"Live API unavailable ({exc}). Showing demo feed."
    note = (
        ""
        if force_demo
        else "No RAPIDAPI_KEY set - showing the demo feed generated from the local database."
    )
    return demo_matches(kind), "demo", note


@st.cache_data(ttl=max(settings.api_cache_seconds, 5), show_spinner=False)
def _fetch_scorecard(match_id: int):
    return parse_scorecard(_client().scorecard(match_id))


def get_scorecard(match: dict, source: str) -> tuple[list[dict], str]:
    if source == "api":
        try:
            return _fetch_scorecard(int(match["match_id"])), ""
        except (CricbuzzAPIError, ValueError) as exc:
            return demo_scorecard(
                match
            ), f"Scorecard unavailable from API ({exc}); showing a simulated card."
    return demo_scorecard(match), ""


# ----------------------------------------------------------------- demo feed
def _rng(*parts) -> random.Random:
    return random.Random(int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16))


def _fmt_score(runs, wkts):
    return f"{runs}/{wkts}" if wkts != 10 else str(runs)
def overs_to_balls(overs):
    whole = int(float(overs))
    balls = round((float(overs) - whole) * 10)

    if not 0 <= balls < 6:
        raise ValueError(f"Invalid cricket overs notation: {overs}")

    return whole * 6 + balls


def balls_to_overs(balls):
    return f"{balls // 6}.{balls % 6}"

def demo_matches(kind: str) -> list[dict]:
    teams = run_query("SELECT team_name, short_name FROM teams ORDER BY team_id")
    venues = run_query("SELECT venue_name, city FROM venues ORDER BY venue_id")
    if len(teams) < 8 or venues.empty:
        return []
    today = datetime.now(timezone.utc).date().toordinal()
    r = _rng("demo", today // 1, kind)
    pairs = []
    pool = list(range(len(teams)))
    r.shuffle(pool)
    for i in range(0, 8, 2):
        pairs.append((pool[i], pool[i + 1]))
    spec = {
        "live": [("T20I", "In Progress"), ("ODI", "In Progress"), ("Test", "Stumps")],
        "recent": [
            ("ODI", "Complete"),
            ("T20I", "Complete"),
            ("Test", "Complete"),
            ("T20I", "Complete"),
        ],
        "upcoming": [
            ("T20I", "Upcoming"),
            ("ODI", "Upcoming"),
            ("Test", "Upcoming"),
            ("ODI", "Upcoming"),
        ],
    }[kind]
    out = []
    for n, ((a, b), (fmt, state)) in enumerate(zip(pairs, spec)):
        ta, tb = teams.iloc[a], teams.iloc[b]
        v = venues.iloc[r.randrange(len(venues))]
        mid = 900000 + zlib.crc32(f"{kind}|{n}|{today}".encode()) % 90000
        rr = _rng(mid)
        base = {"T20I": 165, "ODI": 285, "Test": 340}[fmt]
        s1 = {
            "runs": base + rr.randint(-40, 40),
            "wkts": rr.randint(3, 9),
            "overs": {"T20I": 20, "ODI": 50, "Test": 96}[fmt] - 0.0,
        }
        full = fmt != "Test"
        if state == "Upcoming":
            sc1 = sc2 = {"innings": [], "summary": "Yet to bat", "runs": None}
            status = "Starts " + (datetime.now() + timedelta(days=1 + n, hours=3)).strftime(
                "%a %d %b, %H:%M"
            )
        elif state == "Complete":
            second = s1["runs"] + rr.choice([-37, -12, 18, 24, 44])
            second_overs = balls_to_overs(
                overs_to_balls(s1["overs"]) - 8
            )
            sc1 = {
                "innings": [{"runs": s1["runs"], "wkts": s1["wkts"], "overs": s1["overs"]}],
                "summary": _fmt_score(s1["runs"], s1["wkts"]),
                "runs": s1["runs"],
                "wkts": s1["wkts"],
                "overs": s1["overs"],
            }
            w2 = rr.randint(2, 9)
            sc2 = {
                "innings": [{"runs": second, "wkts": w2, "overs": second_overs}],
                "summary": _fmt_score(second, w2),
                "runs": second,
                "wkts": w2,
                "overs": second_overs
            }
            status = (
                f"{tb['team_name']} won by {10 - w2} wickets"
                if second > s1["runs"]
                else f"{ta['team_name']} won by {s1['runs'] - second} runs"
            )
        else:
            if full:
                total_balls = overs_to_balls(s1["overs"])
                ov_balls = rr.randint(36, total_balls - 12)
                ov = balls_to_overs(ov_balls)
                cur = int(s1["runs"] * ov_balls / total_balls * 1.05)
            else:
                ov = 61.3
                cur = int(
                    s1["runs"]
                    * overs_to_balls(ov)
                    / overs_to_balls(s1["overs"])
                )

            if full:
                sc1 = {
                    "innings": [
                        {
                            "runs": s1["runs"],
                            "wkts": s1["wkts"],
                            "overs": s1["overs"],
                        }
                    ],
                    "summary": _fmt_score(s1["runs"], s1["wkts"]),
                    "runs": s1["runs"],
                    "wkts": s1["wkts"],
                    "overs": s1["overs"],
                }
            else:
                test_wickets = rr.randint(2, 6)
                sc1 = {
                    "innings": [
                        {
                            "runs": cur,
                            "wkts": test_wickets,
                            "overs": ov,
                        }
                    ],
                    "summary": _fmt_score(cur, test_wickets),
                    "runs": cur,
                    "wkts": test_wickets,
                    "overs": ov,
                }


            if full:
                w = rr.randint(1, 6)
                sc2 = {
                    "innings": [{"runs": cur, "wkts": w, "overs": ov}],
                    "summary": _fmt_score(cur, w),
                    "runs": cur,
                    "wkts": w,
                    "overs": ov,
                }
                need = s1["runs"] + 1 - cur
                remaining_balls = max(
                    0,
                    overs_to_balls(s1["overs"]) - overs_to_balls(ov)
                )
                status = (
                    f"{tb['team_name']} need {need} runs from {remaining_balls} balls"
                )
            else:
                sc2 = {"innings": [], "summary": "Yet to bat", "runs": None}
                status = "Day 2: Stumps - " + ta["team_name"] + " lead the session"
        out.append(
            {
                "match_id": mid,
                "series": f"{ta['short_name']} v {tb['short_name']} {fmt} Series (demo)",
                "desc": f"{n + 1}{['st', 'nd', 'rd', 'th'][min(n, 3)]} {fmt}",
                "format": fmt,
                "state": state,
                "status": status,
                "is_live": kind == "live",
                "team1": ta["team_name"],
                "team1_short": ta["short_name"],
                "team2": tb["team_name"],
                "team2_short": tb["short_name"],
                "score1": sc1,
                "score2": sc2,
                "venue": v["venue_name"],
                "city": v["city"],
                "start": None,
            }
        )
    return out


def demo_scorecard(match: dict) -> list[dict]:
    """Simulated scorecard built from real rows in the local players table."""
    rr = _rng("card", match["match_id"])
    innings = []
    for k, (tname, key) in enumerate([(match["team1"], "score1"), (match["team2"], "score2")]):
        score = match[key]
        if not score.get("runs"):
            continue
        sq = run_query(
            "SELECT p.full_name, p.playing_role FROM players p JOIN teams t ON t.country = p.country "
            "WHERE t.team_name = :t ORDER BY p.player_id LIMIT 11",
            {"t": tname},
        )
        if sq.empty:
            continue
        opp = match["team2"] if k == 0 else match["team1"]
        osq = run_query(
            "SELECT p.full_name FROM players p JOIN teams t ON t.country = p.country "
            "WHERE t.team_name = :t AND p.playing_role IN ('Bowler','All-rounder') ORDER BY p.player_id LIMIT 6",
            {"t": opp},
        )
        total, left = score["runs"], score["runs"]
        weights = [rr.uniform(1.4, 2.4) if i < 4 else rr.uniform(0.3, 1.2) for i in range(11)]
        sw = sum(weights)
        bats = []
        for i, (name, w) in enumerate(zip(sq["full_name"], weights)):
            runs = int(total * w / sw) if i < 10 else max(left, 0)
            left -= runs
            balls = max(1, int(runs / rr.uniform(0.8, 1.5))) if runs else rr.randint(1, 6)
            out = i < score.get("wkts", 10)
            bats.append(
                {
                    "Batter": name,
                    "Dismissal": f"c & b {osq['full_name'].iloc[rr.randrange(len(osq))]}"
                    if out and len(osq)
                    else "not out",
                    "R": runs,
                    "B": balls,
                    "4s": runs // 11,
                    "6s": runs // 28,
                    "SR": round(runs / balls * 100, 1),
                }
            )
        bowls = []
        overs_left = round(float(score.get("overs") or 20))
        for j, name in enumerate(osq["full_name"].tolist()[:5]):
            o = max(1, min(4 if match["format"] == "T20I" else 10, overs_left // max(1, 5 - j)))
            rn = int(total / 5 * rr.uniform(0.7, 1.3))
            bowls.append(
                {
                    "Bowler": name,
                    "O": o,
                    "M": rr.randint(0, 1),
                    "R": rn,
                    "W": rr.randint(0, 3),
                    "Econ": round(rn / o, 2),
                }
            )
        innings.append(
            {
                "team": tname,
                "runs": score["runs"],
                "wkts": score.get("wkts", 0),
                "overs": score.get("overs", 0),
                "run_rate": round(score["runs"] / max(float(score.get("overs") or 1), 1), 2),
                "batting": pd.DataFrame(bats),
                "bowling": pd.DataFrame(bowls),
            }
        )
    return innings


def worm_series(match: dict) -> pd.DataFrame:
    """Simulated cumulative runs-per-over for both innings (used for the 'worm' chart)."""
    rr = _rng("worm", match["match_id"])
    rows = []
    for key, name in (("score1", match["team1"]), ("score2", match["team2"])):
        s = match[key]
        if not s.get("runs"):
            continue
        overs = int(float(s.get("overs") or 20))
        cum, rpo = 0.0, s["runs"] / max(overs, 1)
        for o in range(1, overs + 1):
            cum += max(0.0, rr.gauss(rpo, rpo * 0.45))
            rows.append({"over": o, "team": name, "runs": cum})
        scale = s["runs"] / max(cum, 1)
        for row in rows[-overs:]:
            row["runs"] = round(row["runs"] * scale)
    return pd.DataFrame(rows)


@st.cache_data(ttl=300, show_spinner=False)
def api_top_stats(stats_type: str, match_type: int | None) -> pd.DataFrame:
    """Cricbuzz top-stats table (columns exactly as returned by the API)."""
    from api.parsers import parse_table

    return parse_table(_client().top_stats(stats_type, match_type))
