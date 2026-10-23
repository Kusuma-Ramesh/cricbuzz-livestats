"""Turn raw Cricbuzz JSON into flat, UI-friendly structures. Every accessor is defensive:
a missing key never raises - it simply yields a sensible default."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# Match-state vocabulary used by the Cricbuzz feeds (compared in lower case).
LIVE_STATES = frozenset(
    {"in progress", "live", "innings break", "stumps", "lunch", "tea", "rain", "delay"}
)
COMPLETED_STATES = frozenset({"complete", "completed", "abandoned", "no result"})
NOT_STARTED_STATES = frozenset({"upcoming", "preview", "scheduled", "toss"})
_RESULT_RE = re.compile(r"\b(won by|match tied|match drawn|no result|abandoned)\b", re.I)
_STARTS_RE = re.compile(r"^\s*(match\s+)?starts?\b", re.I)


def _g(d: Any, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
        if d is None:
            return default
    return d


def _score(block: dict | None) -> dict:
    """team score block -> {'runs','wkts','overs','summary','innings':[...]}"""
    innings = []
    if isinstance(block, dict):
        for key in sorted(k for k in block if isinstance(k, str) and k.startswith("inngs")):
            i = block[key]
            if not isinstance(i, dict):
                continue
            innings.append(
                {"runs": i.get("runs", 0), "wkts": i.get("wickets", 10), "overs": i.get("overs", 0)}
            )
    if not innings:
        return {"innings": [], "summary": "Yet to bat", "runs": None}
    last = innings[-1]
    parts = [f"{i['runs']}/{i['wkts']}" if i["wkts"] != 10 else str(i["runs"]) for i in innings]
    return {
        "innings": innings,
        "summary": " & ".join(parts),
        "runs": last["runs"],
        "overs": last["overs"],
        "wkts": last["wkts"],
    }


def _ts(ms: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _dicts(seq: Any) -> list[dict]:
    """Only the dict items of a list (anything else - None, str, numbers - is ignored)."""
    return [x for x in seq if isinstance(x, dict)] if isinstance(seq, list) else []


def _vals(x: Any) -> list[dict]:
    """Dict items of either a list or a {key: dict} mapping (the API uses both shapes)."""
    if isinstance(x, dict):
        x = list(x.values())
    return _dicts(x)


def parse_matches(payload: dict) -> list[dict]:
    """matches/v1/{live|recent|upcoming} -> list of normalised match dicts."""
    out: list[dict] = []
    if not isinstance(payload, dict):
        return out
    for tm in _dicts(payload.get("typeMatches")):
        for sm in _dicts(tm.get("seriesMatches")):
            wrap = sm.get("seriesAdWrapper")
            wrap = wrap if isinstance(wrap, dict) else {}
            for match in _dicts(wrap.get("matches")):
                info, sc = match.get("matchInfo"), match.get("matchScore")
                info = info if isinstance(info, dict) else {}
                sc = sc if isinstance(sc, dict) else {}
                state = (info.get("state") or "").strip()
                out.append(
                    {
                        "match_id": info.get("matchId"),
                        "series": info.get("seriesName") or wrap.get("seriesName", ""),
                        "desc": info.get("matchDesc", ""),
                        "format": info.get("matchFormat", ""),
                        "state": state,
                        "status": info.get("status", ""),
                        "is_live": state.lower() in LIVE_STATES,
                        "team1": _g(info, "team1", "teamName", default="Team 1"),
                        "team1_short": _g(info, "team1", "teamSName", default="T1"),
                        "team2": _g(info, "team2", "teamName", default="Team 2"),
                        "team2_short": _g(info, "team2", "teamSName", default="T2"),
                        "score1": _score(sc.get("team1Score")),
                        "score2": _score(sc.get("team2Score")),
                        "venue": _g(info, "venueInfo", "ground", default=""),
                        "city": _g(info, "venueInfo", "city", default=""),
                        "start": _ts(info.get("startDate")),
                    }
                )
    return out


def parse_scorecard(payload: dict) -> list[dict]:
    """mcenter/v1/{id}/scard -> list of innings with batting & bowling DataFrames.

    Never raises on an unexpected shape: anything it cannot read simply yields no innings.
    """
    cards = payload.get("scoreCard") if isinstance(payload, dict) else None
    innings = []
    for inn in _vals(cards):
        bat = inn.get("batTeamDetails") if isinstance(inn.get("batTeamDetails"), dict) else {}
        bowl = inn.get("bowlTeamDetails") if isinstance(inn.get("bowlTeamDetails"), dict) else {}
        sd = inn.get("scoreDetails") if isinstance(inn.get("scoreDetails"), dict) else {}
        bat_rows = _vals(bat.get("batsmenData"))
        bowl_rows = _vals(bowl.get("bowlersData"))
        if not (bat_rows or bowl_rows or sd):
            continue  # an innings block with nothing readable in it
        bats = [
            {
                "Batter": b.get("batName"),
                "Dismissal": b.get("outDesc") or "not out",
                "R": b.get("runs", 0),
                "B": b.get("balls", 0),
                "4s": b.get("fours", 0),
                "6s": b.get("sixes", 0),
                "SR": b.get("strikeRate", 0),
            }
            for b in bat_rows
        ]
        bowls = [
            {
                "Bowler": b.get("bowlName"),
                "O": b.get("overs", 0),
                "M": b.get("maidens", 0),
                "R": b.get("runs", 0),
                "W": b.get("wickets", 0),
                "Econ": b.get("economy", 0),
            }
            for b in bowl_rows
        ]
        wkts = sd.get("wickets")
        if wkts is None:  # the API omits the field when a side is all out: count the dismissals
            wkts = min(10, sum(1 for b in bat_rows if b.get("outDesc")))
        innings.append(
            {
                "team": bat.get("batTeamName", ""),
                "runs": sd.get("runs", 0),
                "wkts": wkts,
                "overs": sd.get("overs", 0),
                "run_rate": sd.get("runRate", 0),
                "batting": pd.DataFrame(bats),
                "bowling": pd.DataFrame(bowls),
            }
        )
    return innings


def match_phase(m: dict) -> str:
    """'completed' | 'live' | 'upcoming' | 'unknown' for a normalised match dict.

    Uses every signal available (state, result text in the status, scores already on the
    board, scheduled start) so one missing field never makes a finished match look unstarted.
    """
    if not isinstance(m, dict):
        return "unknown"
    state = str(m.get("state") or "").strip().lower()
    status = str(m.get("status") or "")
    if state in COMPLETED_STATES or _RESULT_RE.search(status):
        return "completed"
    if state in LIVE_STATES or m.get("is_live"):
        return "live"
    if any(isinstance(m.get(k), dict) and m[k].get("runs") is not None for k in ("score1", "score2")):
        return "live"  # runs are on the board, so play has started
    if state in NOT_STARTED_STATES or _STARTS_RE.search(status):
        return "upcoming"
    start = m.get("start")
    if isinstance(start, datetime) and start > datetime.now(timezone.utc):
        return "upcoming"
    return "unknown"


def innings_totals(m: dict) -> list[dict]:
    """Per-innings totals taken from the match feed itself (genuine data, no scorecard needed)."""
    rows = []
    for key, team in (("score1", "team1"), ("score2", "team2")):
        score = m.get(key) if isinstance(m, dict) else None
        for n, inn in enumerate((score or {}).get("innings") or [], start=1):
            wk = inn.get("wkts")
            runs = inn.get("runs")
            rows.append(
                {
                    "Team": m.get(team, ""),
                    "Innings": n,
                    "Score": str(runs) if wk == 10 else f"{runs}/{wk}",
                    "Overs": inn.get("overs"),
                }
            )
    return rows


def empty_scorecard_message(m: dict) -> tuple[str, str]:
    """(level, text) to show when no detailed scorecard is available; level is 'info'|'warning'.

    'Scorecard will appear once the match starts' is only correct for matches that have not started.
    """
    phase = match_phase(m)
    if phase == "upcoming":
        return "info", "Scorecard will appear once the match starts."
    extra = " Innings totals from the match feed are shown below." if innings_totals(m) else ""
    if phase == "completed":
        return (
            "warning",
            "This match is complete, but the API did not return a detailed scorecard for it." + extra,
        )
    if phase == "live":
        return "info", "Play is under way, but no detailed scorecard has been published yet." + extra
    return "info", "No detailed scorecard is available for this match." + extra


def parse_table(payload: dict, leading_id: str | None = None) -> pd.DataFrame:
    """Generic parser for {'headers': [...], 'values': [{'values': [...]}, ...]} tables
    (used by topstats and player career endpoints).

    The top-stats endpoint sends one more value per row than it sends headers: the first value is
    the player id and has no header, so every label would sit one column to the left.  Pass
    ``leading_id="player_id"`` to name that first column and align the headers with their data.
    """
    if not isinstance(payload, dict):
        return pd.DataFrame()
    headers = list(payload.get("headers") or [])
    raw_rows = payload.get("values")
    rows = [
        r.get("values", []) if isinstance(r, dict) else r
        for r in (raw_rows if isinstance(raw_rows, list) else [])
    ]
    rows = [list(r) for r in rows if isinstance(r, (list, tuple))]
    if not rows:
        return pd.DataFrame()
    width = max(len(r) for r in rows)
    if leading_id and width == len(headers) + 1:
        headers = [leading_id] + headers
    cols = headers + [f"col_{i}" for i in range(len(headers), width)]
    df = pd.DataFrame([r + [None] * (width - len(r)) for r in rows], columns=cols[:width])
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass
    return df


def _is_ordered(values: list, ascending: bool) -> bool:
    pairs = list(zip(values, values[1:]))
    if not pairs or len(set(values)) < 2:
        return False
    return all(a <= b for a, b in pairs) if ascending else all(a >= b for a, b in pairs)


def build_api_board(df: pd.DataFrame, ascending: bool = False) -> pd.DataFrame:
    """API top-stats table -> leaderboard frame with 'name', 'value' and 'sub' columns.

    The API returns the table already ranked by the requested statistic, so the value column is
    the numeric column whose values run in that same order (descending, or ascending for
    'lowest ...' stats).  Falls back to the last numeric column.  Returns an empty frame when the
    table has no name column or no numeric column.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    text_cols = [c for c in df.columns if c not in num_cols]  # object *and* pandas 'str' dtypes
    if not text_cols or not num_cols:
        return pd.DataFrame()
    name_col = text_cols[0] if len(text_cols) == 1 else text_cols[1]
    candidates = [c for c in num_cols if c != "player_id"] or num_cols
    ranked = [c for c in candidates if _is_ordered(df[c].dropna().tolist(), ascending)]
    val_col = ranked[0] if ranked else candidates[-1]
    board = df.rename(columns={name_col: "name", val_col: "value"}).assign(sub="")
    if "M" in board and pd.api.types.is_numeric_dtype(board["M"]):
        board["sub"] = board["M"].map(lambda v: f"{int(v)} matches" if pd.notna(v) else "")
    return board