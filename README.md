# 🏏 Cricbuzz LiveStats

Real-time cricket insights and SQL analytics - a multi-page Streamlit application backed by a
normalised SQLite database and the Cricbuzz Cricket API (RapidAPI).

| Page | What it does |
|---|---|
| **Home** | Project overview, KPI tiles, rated player cards, latest results, team form, architecture and folder map |
| **Live Matches** | Live / recent / upcoming match cards, scorecards, venue, SQL-based head-to-head edge, optional 30 s auto-refresh |
| **Top Player Stats** | Podium + leaderboards (runs, HS, average, SR, centuries, wickets, economy, ...) per format - from the API or SQL |
| **SQL Analytics** | The 25 questions (explanation, SQL, result, chart, CSV), an insight dashboard and a read-only SQL console |
| **CRUD Studio** | One page, entity selector for **Players, Matches, Batting, Bowling**; validation, transactions, audit trail |
| **Player Duel** | Radar + cards + per-format table + form strip for any two players *(extra)* |
| **Stat Arcade** | Higher-or-Lower and Guess-the-Total with XP and streaks *(extra)* |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then add your RAPIDAPI_KEY (optional)
streamlit run main.py
```

On first launch the app creates `data/cricbuzz.db` and fills it with a **fictional** demo dataset
(about 1,300 matches, 150 players, ~54k performance rows) in a couple of seconds.
Without an API key the Live Matches / Top Players pages use a clearly labelled demo feed.

### Cricbuzz API key
1. Subscribe (free tier) to **Cricbuzz Cricket** on RapidAPI.
2. Put the key in `.env` (`RAPIDAPI_KEY=...`) or in `.streamlit/secrets.toml`:
   ```toml
   RAPIDAPI_KEY = "your-key"
   ```
3. Restart the app. The HUD badge changes from `DEMO FEED` to `LIVE API`.

> The endpoint paths in `api/cricbuzz_client.py` follow the RapidAPI playground, but I could not call
> the live API from the build environment. If a page shows "Endpoint not found" or empty tables,
> compare the path/parameters with your playground and adjust that one method.

### Database
SQLite only (the schema, the 25 queries and the tests are verified on SQLite). Override the file
location with `DATABASE_URL=sqlite:///data/cricbuzz.db`. Other engines are not claimed to work.

* `sql/schema.sql` - tables, indexes, constraints, views
* `sql/sample_data.sql` - the demo dataset as INSERTs (`sqlite3 my.db < schema.sql; sqlite3 my.db < sample_data.sql`)
* `sql/queries.sql` - the 25 queries (replace `:today`, `:d30`, `:d3y` with ISO dates)
* Rebuild anytime: `python scripts/seed_database.py` or the sidebar *Maintenance -> Re-seed*.
  Dates are generated relative to the day you seed, so "last 30 days" always has data.

### Real data
`python scripts/sync_from_api.py --players` loads teams and squads from the API (best effort, key required).

## Project layout
```
main.py              router + shared HUD / ticker / sidebar
pages/               home, live_matches, top_players, sql_analytics, crud_studio, player_duel, stat_arcade
api/                 cricbuzz_client.py (retry/back-off), parsers.py
services/            analytics.py, crud.py, live_service.py
utils/               config, db_connection (central), queries (25 SQL), theme, charts, layout, overs
database/            models.py (schema), seed.py (synthetic data)
sql/  scripts/  tests/  docs/
```
See `docs/ARCHITECTURE.md` for the data flow and design decisions.

## Decisions baked in
* Q23 counts scores **strictly above 50**.
* Queries contain **only the filters the brief asks for**; big results are paginated in the UI.
* Bowling is stored as **legal balls**; the UI shows cricket notation (`4.3` = 4 overs 3 balls).
* Batting average = runs / (innings - **not_outs**).
* Demo names/stats are **fictional**; team and venue names are real.
* Code is formatted with `ruff format` at 100 columns (only embedded SQL/HTML/CSS strings run longer).

## Tests
```bash
pip install pytest
python -m pytest -q          # 54 tests: overs, all 25 queries, CRUD validation, SQL-console safety
```

## Security notes
Keys live in `.env` / secrets (git-ignored). All SQL is parameterised. The SQL console allows a single
SELECT on a read-only connection. Deleting players/matches needs a typed confirmation.
