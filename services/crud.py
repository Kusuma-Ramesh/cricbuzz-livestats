"""Create / Read / Update / Delete for players, matches and career stats.

Rules: validate first, write inside one transaction, record an audit row, and never
build SQL by string-formatting user input (everything is bound parameters).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text

from utils import overs
from utils.db_connection import run_query, transaction

ROLES = ["Batsman", "Bowler", "All-rounder", "Wicket-keeper"]
BAT_STYLES = ["Right-hand bat", "Left-hand bat"]
BOWL_STYLES = [
    "Does not bowl",
    "Right-arm fast",
    "Right-arm fast-medium",
    "Left-arm fast",
    "Right-arm medium",
    "Right-arm off-break",
    "Left-arm orthodox",
    "Right-arm leg-break",
    "Left-arm wrist-spin",
]


class ValidationError(ValueError):
    """User-input problem (shown as a friendly warning, not a crash)."""


def _audit(conn, action: str, entity: str, entity_id: int | None, detail: str) -> None:
    conn.execute(
        text("INSERT INTO audit_log (action, entity, entity_id, detail) VALUES (:a, :e, :i, :d)"),
        {"a": action, "e": entity, "i": entity_id, "d": detail[:390]},
    )


# ------------------------------------------------------------------ players
def _validate_player(d: dict[str, Any]) -> dict[str, Any]:
    name = (d.get("full_name") or "").strip()
    if len(name) < 3:
        raise ValidationError("Full name must have at least 3 characters.")
    if len(name) > 120:
        raise ValidationError("Full name is too long (max 120).")
    if not (d.get("country") or "").strip():
        raise ValidationError("Country is required.")
    if d.get("playing_role") not in ROLES:
        raise ValidationError(f"Playing role must be one of {', '.join(ROLES)}.")
    dob = d.get("date_of_birth")
    if dob and dob > date.today():
        raise ValidationError("Date of birth cannot be in the future.")
    bowl = d.get("bowling_style")
    return {
        "full_name": name,
        "country": d["country"].strip(),
        "playing_role": d["playing_role"],
        "batting_style": d.get("batting_style"),
        "bowling_style": None if bowl in (None, "", "Does not bowl") else bowl,
        "date_of_birth": dob.isoformat() if dob else None,
    }


def list_players(
    search: str = "", country: str = "All", role: str = "All", limit: int = 500
) -> pd.DataFrame:
    sql = (
        "SELECT player_id, full_name, country, playing_role, batting_style, bowling_style, date_of_birth "
        "FROM players WHERE 1=1"
    )
    params: dict[str, Any] = {}
    if search:
        sql += " AND LOWER(full_name) LIKE :s"
        params["s"] = f"%{search.lower()}%"
    if country != "All":
        sql += " AND country = :c"
        params["c"] = country
    if role != "All":
        sql += " AND playing_role = :r"
        params["r"] = role
    return run_query(sql + f" ORDER BY player_id DESC LIMIT {int(limit)}", params)


def create_player(data: dict[str, Any]) -> int:
    v = _validate_player(data)
    with transaction() as conn:
        dup = conn.execute(
            text("SELECT COUNT(*) FROM players WHERE LOWER(full_name)=:n AND country=:c"),
            {"n": v["full_name"].lower(), "c": v["country"]},
        ).scalar()
        if dup:
            raise ValidationError("A player with this name already exists for that country.")
        res = conn.execute(
            text(
                "INSERT INTO players (full_name, country, playing_role, batting_style, bowling_style, date_of_birth) "
                "VALUES (:full_name, :country, :playing_role, :batting_style, :bowling_style, :date_of_birth)"
            ),
            v,
        )
        new_id = res.lastrowid or conn.execute(text("SELECT MAX(player_id) FROM players")).scalar()
        _audit(conn, "CREATE", "player", new_id, f"{v['full_name']} ({v['country']})")
    return int(new_id)


def update_player(player_id: int, data: dict[str, Any]) -> None:
    v = _validate_player(data)
    with transaction() as conn:
        n = conn.execute(
            text(
                "UPDATE players SET full_name=:full_name, country=:country, playing_role=:playing_role, "
                "batting_style=:batting_style, bowling_style=:bowling_style, date_of_birth=:date_of_birth WHERE player_id=:id"
            ),
            {**v, "id": player_id},
        ).rowcount
        if n == 0:
            raise ValidationError("Player not found.")
        _audit(conn, "UPDATE", "player", player_id, f"{v['full_name']} -> role {v['playing_role']}")


def player_usage(player_id: int) -> dict[str, int]:
    q = lambda t: int(
        run_query(f"SELECT COUNT(*) AS n FROM {t} WHERE player_id = :p", {"p": player_id}).iloc[
            0, 0
        ]
    )
    return {
        "batting": q("batting_performances"),
        "bowling": q("bowling_performances"),
        "fielding": q("fielding_performances"),
        "career": q("player_career_stats"),
    }


def delete_player(player_id: int, cascade: bool = False) -> None:
    usage = player_usage(player_id)
    refs = usage["batting"] + usage["bowling"] + usage["fielding"]
    if refs and not cascade:
        raise ValidationError(
            f"Player has {refs} performance rows. Tick 'cascade' to delete them too."
        )
    with transaction() as conn:
        for t in (
            "batting_performances",
            "bowling_performances",
            "fielding_performances",
            "player_career_stats",
        ):
            conn.execute(text(f"DELETE FROM {t} WHERE player_id = :p"), {"p": player_id})
        n = conn.execute(
            text("DELETE FROM players WHERE player_id = :p"), {"p": player_id}
        ).rowcount
        if n == 0:
            raise ValidationError("Player not found.")
        _audit(conn, "DELETE", "player", player_id, f"cascade={cascade}, rows={refs}")


# ------------------------------------------------------------------ matches
def list_matches(fmt: str = "All", team: str = "All", limit: int = 300) -> pd.DataFrame:
    sql = (
        "SELECT m.match_id, m.match_date, m.match_format, m.description, t1.team_name AS team_1, t2.team_name AS team_2, "
        "w.team_name AS winner, m.victory_margin, m.victory_type, v.venue_name FROM matches m "
        "JOIN teams t1 ON t1.team_id=m.team1_id JOIN teams t2 ON t2.team_id=m.team2_id "
        "JOIN venues v ON v.venue_id=m.venue_id LEFT JOIN teams w ON w.team_id=m.winner_id WHERE 1=1"
    )
    params: dict[str, Any] = {}
    if fmt != "All":
        sql += " AND m.match_format = :f"
        params["f"] = fmt
    if team != "All":
        sql += " AND (t1.team_name = :t OR t2.team_name = :t)"
        params["t"] = team
    return run_query(
        sql + f" ORDER BY m.match_date DESC, m.match_id DESC LIMIT {int(limit)}", params
    )


def lookups() -> dict[str, pd.DataFrame]:
    return {
        "teams": run_query("SELECT team_id, team_name FROM teams ORDER BY team_name"),
        "venues": run_query("SELECT venue_id, venue_name, city FROM venues ORDER BY venue_name"),
        "series": run_query(
            "SELECT series_id, series_name FROM series ORDER BY start_date DESC LIMIT 200"
        ),
    }


def _validate_match(d: dict[str, Any]) -> dict[str, Any]:
    if d["team1_id"] == d["team2_id"]:
        raise ValidationError("A team cannot play against itself.")
    if d["match_date"] > date.today():
        raise ValidationError("Completed matches cannot be dated in the future.")
    if d.get("winner_id") and d["winner_id"] not in (d["team1_id"], d["team2_id"]):
        raise ValidationError("The winner must be one of the two teams.")
    if d.get("toss_winner_id") and d["toss_winner_id"] not in (d["team1_id"], d["team2_id"]):
        raise ValidationError("The toss winner must be one of the two teams.")
    if d.get("winner_id") and (
        not d.get("victory_type") or not d.get("victory_margin") or d["victory_margin"] < 1
    ):
        raise ValidationError("Provide a victory type and a margin of at least 1.")
    dt = d["match_date"]
    return {
        **d,
        "match_date": dt.isoformat(),
        "match_year": dt.year,
        "year_quarter": f"{dt.year}-Q{(dt.month - 1) // 3 + 1}",
        "victory_type": d.get("victory_type") if d.get("winner_id") else None,
        "victory_margin": d.get("victory_margin") if d.get("winner_id") else None,
    }


def create_match(d: dict[str, Any]) -> int:
    v = _validate_match(d)
    with transaction() as conn:
        res = conn.execute(
            text(
                "INSERT INTO matches (series_id, description, match_format, team1_id, team2_id, venue_id, match_date, match_year, "
                "year_quarter, toss_winner_id, toss_decision, winner_id, victory_margin, victory_type, status) VALUES "
                "(:series_id, :description, :match_format, :team1_id, :team2_id, :venue_id, :match_date, :match_year, "
                ":year_quarter, :toss_winner_id, :toss_decision, :winner_id, :victory_margin, :victory_type, 'Completed')"
            ),
            v,
        )
        new_id = res.lastrowid or conn.execute(text("SELECT MAX(match_id) FROM matches")).scalar()
        _audit(conn, "CREATE", "match", new_id, v["description"])
    return int(new_id)


def update_match_result(
    match_id: int, winner_id: int | None, margin: int | None, vtype: str | None
) -> None:
    row = run_query("SELECT team1_id, team2_id FROM matches WHERE match_id = :m", {"m": match_id})
    if row.empty:
        raise ValidationError("Match not found.")
    if winner_id and winner_id not in (int(row.iloc[0, 0]), int(row.iloc[0, 1])):
        raise ValidationError("The winner must be one of the two teams.")
    if winner_id and (not vtype or not margin or margin < 1):
        raise ValidationError("Provide a victory type and a margin of at least 1.")
    with transaction() as conn:
        conn.execute(
            text(
                "UPDATE matches SET winner_id=:w, victory_margin=:m, victory_type=:t WHERE match_id=:id"
            ),
            {
                "w": winner_id,
                "m": margin if winner_id else None,
                "t": vtype if winner_id else None,
                "id": match_id,
            },
        )
        _audit(conn, "UPDATE", "match", match_id, f"winner={winner_id} margin={margin} {vtype}")


def delete_match(match_id: int) -> None:
    with transaction() as conn:
        for t in ("batting_performances", "bowling_performances", "fielding_performances"):
            conn.execute(text(f"DELETE FROM {t} WHERE match_id = :m"), {"m": match_id})
        n = conn.execute(text("DELETE FROM matches WHERE match_id = :m"), {"m": match_id}).rowcount
        if n == 0:
            raise ValidationError("Match not found.")
        _audit(conn, "DELETE", "match", match_id, "match and child performances removed")


# ------------------------------------------------------------------ batting / bowling
def _refresh_career() -> None:
    """Career stats are derived data; rebuild them after any performance write."""
    from database.seed import refresh_career_stats
    from utils.db_connection import get_engine

    refresh_career_stats(get_engine())


def _check_match_player(conn, match_id: int, player_id: int, team_id: int) -> None:
    row = conn.execute(
        text("SELECT team1_id, team2_id FROM matches WHERE match_id=:m"), {"m": match_id}
    ).first()
    if row is None:
        raise ValidationError("Match not found.")
    if team_id not in (row[0], row[1]):
        raise ValidationError("The team must be one of the two teams in this match.")
    if (
        conn.execute(
            text("SELECT COUNT(*) FROM players WHERE player_id=:p"), {"p": player_id}
        ).scalar()
        == 0
    ):
        raise ValidationError("Player not found.")


def list_batting(match_id: int | None = None, search: str = "", limit: int = 300) -> pd.DataFrame:
    sql = (
        "SELECT b.perf_id, m.match_date, m.description, b.innings_no, p.full_name AS player, b.batting_position AS pos, "
        "b.runs, b.balls_faced AS balls, b.fours, b.sixes, b.strike_rate, b.is_out FROM batting_performances b "
        "JOIN matches m ON m.match_id=b.match_id JOIN players p ON p.player_id=b.player_id WHERE 1=1"
    )
    params: dict[str, Any] = {}
    if match_id:
        sql += " AND b.match_id = :m"
        params["m"] = match_id
    if search:
        sql += " AND LOWER(p.full_name) LIKE :s"
        params["s"] = f"%{search.lower()}%"
    return run_query(
        sql + f" ORDER BY m.match_date DESC, b.perf_id DESC LIMIT {int(limit)}", params
    )


def _validate_batting(d: dict[str, Any]) -> dict[str, Any]:
    for k in ("runs", "balls_faced", "fours", "sixes"):
        if int(d[k]) < 0:
            raise ValidationError(f"{k.replace('_', ' ').title()} cannot be negative.")
    if not 1 <= int(d["batting_position"]) <= 11:
        raise ValidationError("Batting position must be between 1 and 11.")
    if not 1 <= int(d["innings_no"]) <= 4:
        raise ValidationError("Innings number must be between 1 and 4.")
    if int(d["fours"]) * 4 + int(d["sixes"]) * 6 > int(d["runs"]):
        raise ValidationError("Boundaries (4s x 4 + 6s x 6) cannot exceed the runs scored.")
    if int(d["runs"]) > 0 and int(d["balls_faced"]) == 0:
        raise ValidationError("A batter who scored runs must have faced at least one ball.")
    balls = int(d["balls_faced"])
    return {
        **{
            k: int(d[k])
            for k in (
                "match_id",
                "innings_no",
                "player_id",
                "team_id",
                "batting_position",
                "runs",
                "balls_faced",
                "fours",
                "sixes",
            )
        },
        "is_out": 1 if d["is_out"] else 0,
        "sr": round(int(d["runs"]) * 100.0 / balls, 2) if balls else None,
    }


def create_batting(d: dict[str, Any]) -> int:
    v = _validate_batting(d)
    with transaction() as conn:
        _check_match_player(conn, v["match_id"], v["player_id"], v["team_id"])
        dup = conn.execute(
            text(
                "SELECT COUNT(*) FROM batting_performances WHERE match_id=:match_id AND "
                "innings_no=:innings_no AND player_id=:player_id"
            ),
            v,
        ).scalar()
        if dup:
            raise ValidationError(
                "That player already has a batting row for this match and innings."
            )
        res = conn.execute(
            text(
                "INSERT INTO batting_performances (match_id, innings_no, player_id, team_id, batting_position, runs, "
                "balls_faced, fours, sixes, strike_rate, is_out) VALUES (:match_id, :innings_no, :player_id, :team_id, "
                ":batting_position, :runs, :balls_faced, :fours, :sixes, :sr, :is_out)"
            ),
            v,
        )
        new_id = (
            res.lastrowid
            or conn.execute(text("SELECT MAX(perf_id) FROM batting_performances")).scalar()
        )
        _audit(
            conn,
            "CREATE",
            "batting",
            new_id,
            f"match {v['match_id']} player {v['player_id']} runs {v['runs']}",
        )
    _refresh_career()
    return int(new_id)


def update_batting(perf_id: int, d: dict[str, Any]) -> None:
    v = _validate_batting(d)
    with transaction() as conn:
        _check_match_player(conn, v["match_id"], v["player_id"], v["team_id"])
        n = conn.execute(
            text(
                "UPDATE batting_performances SET innings_no=:innings_no, batting_position=:batting_position, runs=:runs, "
                "balls_faced=:balls_faced, fours=:fours, sixes=:sixes, strike_rate=:sr, is_out=:is_out WHERE perf_id=:id"
            ),
            {**v, "id": perf_id},
        ).rowcount
        if n == 0:
            raise ValidationError("Batting row not found.")
        _audit(conn, "UPDATE", "batting", perf_id, f"runs {v['runs']} balls {v['balls_faced']}")
    _refresh_career()


def delete_batting(perf_id: int) -> None:
    with transaction() as conn:
        if (
            conn.execute(
                text("DELETE FROM batting_performances WHERE perf_id=:i"), {"i": perf_id}
            ).rowcount
            == 0
        ):
            raise ValidationError("Batting row not found.")
        _audit(conn, "DELETE", "batting", perf_id, "performance removed")
    _refresh_career()


def list_bowling(match_id: int | None = None, search: str = "", limit: int = 300) -> pd.DataFrame:
    sql = (
        "SELECT w.perf_id, m.match_date, m.description, w.innings_no, p.full_name AS player, w.legal_balls, "
        "w.maidens, w.runs_conceded AS runs, w.wickets, w.economy FROM bowling_performances w "
        "JOIN matches m ON m.match_id=w.match_id JOIN players p ON p.player_id=w.player_id WHERE 1=1"
    )
    params: dict[str, Any] = {}
    if match_id:
        sql += " AND w.match_id = :m"
        params["m"] = match_id
    if search:
        sql += " AND LOWER(p.full_name) LIKE :s"
        params["s"] = f"%{search.lower()}%"
    df = run_query(sql + f" ORDER BY m.match_date DESC, w.perf_id DESC LIMIT {int(limit)}", params)
    if not df.empty:
        df.insert(
            df.columns.get_loc("legal_balls"), "overs", df["legal_balls"].map(overs.to_notation)
        )
    return df


def _validate_bowling(d: dict[str, Any]) -> dict[str, Any]:
    try:
        balls = overs.to_balls(d["overs"])
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if balls <= 0:
        raise ValidationError("A bowler must have bowled at least one legal ball.")
    if not 1 <= int(d["innings_no"]) <= 4:
        raise ValidationError("Innings number must be between 1 and 4.")
    if int(d["runs_conceded"]) < 0 or int(d["maidens"]) < 0:
        raise ValidationError("Runs and maidens cannot be negative.")
    if not 0 <= int(d["wickets"]) <= 10:
        raise ValidationError("Wickets must be between 0 and 10.")
    if int(d["maidens"]) > balls // 6:
        raise ValidationError("Maidens cannot exceed the number of completed overs.")
    return {
        **{
            k: int(d[k])
            for k in ("match_id", "innings_no", "player_id", "team_id", "maidens", "wickets")
        },
        "runs": int(d["runs_conceded"]),
        "balls": balls,
        "econ": overs.economy(int(d["runs_conceded"]), balls),
    }


def create_bowling(d: dict[str, Any]) -> int:
    v = _validate_bowling(d)
    with transaction() as conn:
        _check_match_player(conn, v["match_id"], v["player_id"], v["team_id"])
        dup = conn.execute(
            text(
                "SELECT COUNT(*) FROM bowling_performances WHERE match_id=:match_id AND "
                "innings_no=:innings_no AND player_id=:player_id"
            ),
            v,
        ).scalar()
        if dup:
            raise ValidationError(
                "That player already has a bowling row for this match and innings."
            )
        res = conn.execute(
            text(
                "INSERT INTO bowling_performances (match_id, innings_no, player_id, team_id, legal_balls, maidens, "
                "runs_conceded, wickets, economy) VALUES (:match_id, :innings_no, :player_id, :team_id, :balls, :maidens, "
                ":runs, :wickets, :econ)"
            ),
            v,
        )
        new_id = (
            res.lastrowid
            or conn.execute(text("SELECT MAX(perf_id) FROM bowling_performances")).scalar()
        )
        _audit(
            conn,
            "CREATE",
            "bowling",
            new_id,
            f"match {v['match_id']} player {v['player_id']} {v['wickets']}/{v['runs']}",
        )
    _refresh_career()
    return int(new_id)


def update_bowling(perf_id: int, d: dict[str, Any]) -> None:
    v = _validate_bowling(d)
    with transaction() as conn:
        _check_match_player(conn, v["match_id"], v["player_id"], v["team_id"])
        n = conn.execute(
            text(
                "UPDATE bowling_performances SET innings_no=:innings_no, legal_balls=:balls, maidens=:maidens, "
                "runs_conceded=:runs, wickets=:wickets, economy=:econ WHERE perf_id=:id"
            ),
            {**v, "id": perf_id},
        ).rowcount
        if n == 0:
            raise ValidationError("Bowling row not found.")
        _audit(
            conn,
            "UPDATE",
            "bowling",
            perf_id,
            f"{v['wickets']}/{v['runs']} in {overs.to_notation(v['balls'])}",
        )
    _refresh_career()


def delete_bowling(perf_id: int) -> None:
    with transaction() as conn:
        if (
            conn.execute(
                text("DELETE FROM bowling_performances WHERE perf_id=:i"), {"i": perf_id}
            ).rowcount
            == 0
        ):
            raise ValidationError("Bowling row not found.")
        _audit(conn, "DELETE", "bowling", perf_id, "performance removed")
    _refresh_career()


def match_options(limit: int = 300) -> pd.DataFrame:
    return run_query(
        "SELECT m.match_id, m.match_date, m.description, t1.team_id AS t1_id, t1.team_name AS t1, t2.team_id AS t2_id, "
        "t2.team_name AS t2 FROM matches m JOIN teams t1 ON t1.team_id=m.team1_id JOIN teams t2 ON t2.team_id=m.team2_id "
        f"ORDER BY m.match_date DESC, m.match_id DESC LIMIT {int(limit)}"
    )


def recent_audit(n: int = 12) -> pd.DataFrame:
    return run_query(
        f"SELECT created_at, action, entity, entity_id, detail FROM audit_log ORDER BY log_id DESC LIMIT {int(n)}"
    )
