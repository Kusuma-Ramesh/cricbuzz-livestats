"""Relational schema (SQLAlchemy Core). Tested on SQLite.

Normalisation: 3NF. Dimensions (teams, venues, players, series) are referenced by
integer keys from the fact tables (matches, batting/bowling/fielding performances).
`match_year` / `year_quarter` on matches are deliberate, documented denormalisations
so that time-series SQL stays simple. Bowling is stored as legal balls (4.3 overs = 27 balls).
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
)

metadata = MetaData()

teams = Table(
    "teams",
    metadata,
    Column("team_id", Integer, primary_key=True, autoincrement=True),
    Column("team_name", String(80), nullable=False, unique=True),
    Column("short_name", String(8), nullable=False),
    Column("country", String(60), nullable=False),
)

venues = Table(
    "venues",
    metadata,
    Column("venue_id", Integer, primary_key=True, autoincrement=True),
    Column("venue_name", String(120), nullable=False, unique=True),
    Column("city", String(80), nullable=False),
    Column("country", String(60), nullable=False),
    Column("capacity", Integer, CheckConstraint("capacity > 0")),
)

players = Table(
    "players",
    metadata,
    Column("player_id", Integer, primary_key=True, autoincrement=True),
    Column("full_name", String(120), nullable=False),
    Column("country", String(60), nullable=False),
    Column("playing_role", String(30), nullable=False),
    Column("batting_style", String(40)),
    Column("bowling_style", String(40)),
    Column("date_of_birth", Date),
    CheckConstraint(
        "playing_role IN ('Batsman','Bowler','All-rounder','Wicket-keeper')",
        name="ck_players_role",
    ),
)

series = Table(
    "series",
    metadata,
    Column("series_id", Integer, primary_key=True, autoincrement=True),
    Column("series_name", String(160), nullable=False),
    Column("host_country", String(60), nullable=False),
    Column("match_type", String(10), nullable=False),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date),
    Column("total_matches", Integer, nullable=False),
    CheckConstraint("match_type IN ('Test','ODI','T20I')", name="ck_series_type"),
)

matches = Table(
    "matches",
    metadata,
    Column("match_id", Integer, primary_key=True, autoincrement=True),
    Column(
        "series_id", Integer, ForeignKey("series.series_id", ondelete="CASCADE"), nullable=False
    ),
    Column("description", String(200), nullable=False),
    Column("match_format", String(10), nullable=False),
    Column("team1_id", Integer, ForeignKey("teams.team_id"), nullable=False),
    Column("team2_id", Integer, ForeignKey("teams.team_id"), nullable=False),
    Column("venue_id", Integer, ForeignKey("venues.venue_id"), nullable=False),
    Column("match_date", Date, nullable=False),
    Column("match_year", Integer, nullable=False),
    Column("year_quarter", String(8), nullable=False),
    Column("toss_winner_id", Integer, ForeignKey("teams.team_id")),
    Column("toss_decision", String(5)),
    Column("winner_id", Integer, ForeignKey("teams.team_id")),
    Column("victory_margin", Integer),
    Column("victory_type", String(8)),
    Column("status", String(20), nullable=False, server_default="Completed"),
    CheckConstraint("match_format IN ('Test','ODI','T20I')", name="ck_matches_format"),
    CheckConstraint("team1_id <> team2_id", name="ck_matches_teams"),
    CheckConstraint(
        "toss_decision IN ('bat','bowl') OR toss_decision IS NULL", name="ck_matches_toss"
    ),
    CheckConstraint(
        "victory_type IN ('runs','wickets') OR victory_type IS NULL", name="ck_matches_vtype"
    ),
)
Index("ix_matches_date", matches.c.match_date)
Index("ix_matches_format_date", matches.c.match_format, matches.c.match_date)
Index("ix_matches_venue", matches.c.venue_id)
Index("ix_matches_winner", matches.c.winner_id)
Index("ix_matches_teams", matches.c.team1_id, matches.c.team2_id)

batting_performances = Table(
    "batting_performances",
    metadata,
    Column("perf_id", Integer, primary_key=True, autoincrement=True),
    Column("match_id", Integer, ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False),
    Column("innings_no", Integer, nullable=False),
    Column("player_id", Integer, ForeignKey("players.player_id"), nullable=False),
    Column("team_id", Integer, ForeignKey("teams.team_id"), nullable=False),
    Column("batting_position", Integer, nullable=False),
    Column("runs", Integer, nullable=False),
    Column("balls_faced", Integer, nullable=False),
    Column("fours", Integer, nullable=False, server_default="0"),
    Column("sixes", Integer, nullable=False, server_default="0"),
    Column("strike_rate", Float),
    Column("is_out", Integer, nullable=False, server_default="1"),
    UniqueConstraint("match_id", "innings_no", "player_id", name="uq_bat_match_inn_player"),
    CheckConstraint("runs >= 0 AND balls_faced >= 0", name="ck_bat_nonneg"),
)
Index("ix_bat_player", batting_performances.c.player_id)
Index(
    "ix_bat_match_inn_pos",
    batting_performances.c.match_id,
    batting_performances.c.innings_no,
    batting_performances.c.batting_position,
)

bowling_performances = Table(
    "bowling_performances",
    metadata,
    Column("perf_id", Integer, primary_key=True, autoincrement=True),
    Column("match_id", Integer, ForeignKey("matches.match_id", ondelete="CASCADE"), nullable=False),
    Column("innings_no", Integer, nullable=False),
    Column("player_id", Integer, ForeignKey("players.player_id"), nullable=False),
    Column("team_id", Integer, ForeignKey("teams.team_id"), nullable=False),
    Column("legal_balls", Integer, nullable=False),
    Column("maidens", Integer, nullable=False, server_default="0"),
    Column("runs_conceded", Integer, nullable=False),
    Column("wickets", Integer, nullable=False),
    Column("economy", Float),
    UniqueConstraint("match_id", "innings_no", "player_id", name="uq_bowl_match_inn_player"),
    CheckConstraint("legal_balls > 0", name="ck_bowl_balls"),
)
Index("ix_bowl_player", bowling_performances.c.player_id)
Index("ix_bowl_match", bowling_performances.c.match_id)

fielding_performances = Table(
    "fielding_performances",
    metadata,
    Column(
        "match_id", Integer, ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True
    ),
    Column("player_id", Integer, ForeignKey("players.player_id"), primary_key=True),
    Column("catches", Integer, nullable=False, server_default="0"),
    Column("stumpings", Integer, nullable=False, server_default="0"),
)

player_career_stats = Table(
    "player_career_stats",
    metadata,
    Column(
        "player_id", Integer, ForeignKey("players.player_id", ondelete="CASCADE"), primary_key=True
    ),
    Column("match_format", String(10), primary_key=True),
    Column("matches", Integer, nullable=False, server_default="0"),
    Column("innings", Integer, nullable=False, server_default="0"),
    Column("not_outs", Integer, nullable=False, server_default="0"),
    Column("total_runs", Integer, nullable=False, server_default="0"),
    Column("highest_score", Integer, nullable=False, server_default="0"),
    Column("batting_average", Float),
    Column("strike_rate", Float),
    Column("centuries", Integer, nullable=False, server_default="0"),
    Column("fifties", Integer, nullable=False, server_default="0"),
    Column("total_wickets", Integer, nullable=False, server_default="0"),
    Column("bowling_average", Float),
    Column("economy_rate", Float),
    Column("catches", Integer, nullable=False, server_default="0"),
    Column("stumpings", Integer, nullable=False, server_default="0"),
)
Index("ix_career_format_runs", player_career_stats.c.match_format, player_career_stats.c.total_runs)

audit_log = Table(
    "audit_log",
    metadata,
    Column("log_id", Integer, primary_key=True, autoincrement=True),
    Column("action", String(10), nullable=False),
    Column("entity", String(20), nullable=False),
    Column("entity_id", Integer),
    Column("detail", String(400)),
    Column("created_at", DateTime, server_default=func.now()),
)

# Views (portable SELECTs; recreated on every init)
VIEWS = {
    "v_match_results": """
        SELECT m.match_id, m.match_date, m.match_format, m.description,
               t1.team_name AS team1, t2.team_name AS team2,
               w.team_name AS winner, m.victory_margin, m.victory_type,
               v.venue_name, v.city, v.country AS venue_country
        FROM matches m
        JOIN teams t1 ON t1.team_id = m.team1_id
        JOIN teams t2 ON t2.team_id = m.team2_id
        JOIN venues v ON v.venue_id = m.venue_id
        LEFT JOIN teams w ON w.team_id = m.winner_id
    """,
    "v_player_leaderboard": """
        SELECT p.player_id, p.full_name, p.country, p.playing_role,
               SUM(c.total_runs) AS runs, SUM(c.total_wickets) AS wickets,
               SUM(c.matches) AS matches
        FROM players p JOIN player_career_stats c ON c.player_id = p.player_id
        GROUP BY p.player_id, p.full_name, p.country, p.playing_role
    """,
}
