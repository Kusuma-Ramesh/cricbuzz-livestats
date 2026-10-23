"""Best-effort loader: pull international teams (and optionally their players) from the Cricbuzz API
into the local database. Requires RAPIDAPI_KEY. Response shapes can change - verify in the RapidAPI
playground if a field comes back empty.

Usage:  python scripts/sync_from_api.py --players
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from api.cricbuzz_client import CricbuzzAPIError, CricbuzzClient  # noqa: E402
from utils.db_connection import ensure_database, transaction  # noqa: E402

ROLE_MAP = {
    "batsman": "Batsman",
    "batter": "Batsman",
    "bowler": "Bowler",
    "allrounder": "All-rounder",
    "all-rounder": "All-rounder",
    "wk-batsman": "Wicket-keeper",
    "wicketkeeper": "Wicket-keeper",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--players", action="store_true", help="also fetch squads (1 API call per team)"
    )
    args = parser.parse_args()
    ensure_database()
    client = CricbuzzClient()
    try:
        teams = [t for t in client.teams().get("list", []) if t.get("teamId")]
    except CricbuzzAPIError as exc:
        sys.exit(f"API error: {exc}")
    added = 0
    with transaction() as conn:
        for t in teams:
            name, short = (
                t.get("teamName"),
                (t.get("teamSName") or t.get("teamName", "")[:3]).upper(),
            )
            if (
                name
                and not conn.execute(
                    text("SELECT 1 FROM teams WHERE team_name=:n"), {"n": name}
                ).first()
            ):
                conn.execute(
                    text("INSERT INTO teams (team_name, short_name, country) VALUES (:n, :s, :n)"),
                    {"n": name, "s": short},
                )
                added += 1
    print(f"Teams: {len(teams)} fetched, {added} new.")
    if not args.players:
        return
    players_added = 0
    for t in teams:
        try:
            squad = client.team_players(int(t["teamId"])).get("player", [])
        except CricbuzzAPIError as exc:
            print(f"  skipped {t.get('teamName')}: {exc}")
            continue
        with transaction() as conn:
            for p in squad:
                if not p.get("name") or "role" in p and not p.get("id"):
                    continue
                role = ROLE_MAP.get(str(p.get("role", "")).lower().replace(" ", ""), "Batsman")
                if conn.execute(
                    text("SELECT 1 FROM players WHERE full_name=:n AND country=:c"),
                    {"n": p["name"], "c": t["teamName"]},
                ).first():
                    continue
                conn.execute(
                    text(
                        "INSERT INTO players (full_name, country, playing_role, batting_style, bowling_style) "
                        "VALUES (:n, :c, :r, :b, :w)"
                    ),
                    {
                        "n": p["name"],
                        "c": t["teamName"],
                        "r": role,
                        "b": p.get("battingStyle"),
                        "w": p.get("bowlingStyle"),
                    },
                )
                players_added += 1
    print(f"Players: {players_added} new.")


if __name__ == "__main__":
    main()
