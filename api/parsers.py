"""Turn raw Cricbuzz JSON into flat, UI-friendly structures. Every accessor is defensive:
a missing key never raises - it simply yields a sensible default."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


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
        for key in sorted(k for k in block if k.startswith("inngs")):
            i = block[key]
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


def parse_matches(payload: dict) -> list[dict]:
    """matches/v1/{live|recent|upcoming} -> list of normalised match dicts."""
    out: list[dict] = []
    for tm in payload.get("typeMatches", []) or []:
        for sm in tm.get("seriesMatches", []) or []:
            wrap = sm.get("seriesAdWrapper") or {}
            for match in wrap.get("matches", []) or []:
                info, sc = match.get("matchInfo", {}), match.get("matchScore", {})
                state = (info.get("state") or "").strip()
                out.append(
                    {
                        "match_id": info.get("matchId"),
                        "series": info.get("seriesName") or wrap.get("seriesName", ""),
                        "desc": info.get("matchDesc", ""),
                        "format": info.get("matchFormat", ""),
                        "state": state,
                        "status": info.get("status", ""),
                        "is_live": state.lower()
                        in {
                            "in progress",
                            "live",
                            "innings break",
                            "stumps",
                            "lunch",
                            "tea",
                            "rain",
                            "delay",
                        },
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
    """mcenter/v1/{id}/scard -> list of innings with batting & bowling DataFrames."""
    innings = []
    for inn in payload.get("scoreCard", []) or []:
        bat = inn.get("batTeamDetails") or {}
        bowl = inn.get("bowlTeamDetails") or {}
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
            for b in (bat.get("batsmenData") or {}).values()
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
            for b in (bowl.get("bowlersData") or {}).values()
        ]
        sd = inn.get("scoreDetails") or {}
        innings.append(
            {
                "team": bat.get("batTeamName", ""),
                "runs": sd.get("runs", 0),
                "wkts": sd.get("wickets", 0),
                "overs": sd.get("overs", 0),
                "run_rate": sd.get("runRate", 0),
                "batting": pd.DataFrame(bats),
                "bowling": pd.DataFrame(bowls),
            }
        )
    return innings


def parse_table(payload: dict) -> pd.DataFrame:
    """Generic parser for {'headers': [...], 'values': [{'values': [...]}, ...]} tables
    (used by topstats and player career endpoints)."""
    headers = payload.get("headers") or []
    rows = [
        r.get("values", []) if isinstance(r, dict) else r for r in payload.get("values", []) or []
    ]
    if not rows:
        return pd.DataFrame()
    width = max(len(r) for r in rows)
    cols = list(headers) + [f"col_{i}" for i in range(len(headers), width)]
    df = pd.DataFrame([r + [None] * (width - len(r)) for r in rows], columns=cols[:width])
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col])
        except (ValueError, TypeError):
            pass
    return df
