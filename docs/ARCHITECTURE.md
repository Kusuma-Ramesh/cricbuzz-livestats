# Architecture

```
 Cricbuzz API (RapidAPI)                      SQLite (data/cricbuzz.db)
        |                                              ^
  api/cricbuzz_client.py  (retry, rate-limit)          |
  api/parsers.py          (defensive JSON -> dicts)    |
        |                                     utils/db_connection.py
        v                                     (engine, transactions, read-only runner)
  services/live_service.py  <- demo fallback          ^
  services/analytics.py  ------------------------------+
  services/crud.py (validation + audit log) -----------+
        |
        v
  pages/*.py (Streamlit UI)  <-  utils/theme.py, utils/charts.py, utils/layout.py
```

## Data model (3NF)
`teams`, `venues`, `players`, `series` are dimensions. `matches` references them.
`batting_performances`, `bowling_performances`, `fielding_performances` are facts keyed by
match + player. `player_career_stats` is derived (rebuilt after every performance write).
`audit_log` records each CRUD action. Two views: `v_match_results`, `v_player_leaderboard`.

Design decisions
* **Legal balls**: bowling stores `legal_balls` (4.3 overs = 27). `utils/overs.py` converts at the edges.
* **not_outs** on career stats: batting average = runs / (innings - not_outs).
* **matches.match_year / year_quarter** are intentional denormalisations that keep the time-series
  questions (16, 25) simple.
* **Queries carry only the filters the brief requests**; the UI paginates large results.
* **Demo data is fictional** (invented names and statistics). Real data enters through the API pages
  or `scripts/sync_from_api.py`.
* **Security**: secrets come from `.env` / Streamlit secrets; every query is parameterised; the SQL
  console accepts one SELECT and runs on a read-only connection.
