-- Cricbuzz LiveStats schema (SQLite dialect)

CREATE TABLE audit_log (
	log_id INTEGER NOT NULL, 
	action VARCHAR(10) NOT NULL, 
	entity VARCHAR(20) NOT NULL, 
	entity_id INTEGER, 
	detail VARCHAR(400), 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (log_id)
);

CREATE TABLE players (
	player_id INTEGER NOT NULL, 
	full_name VARCHAR(120) NOT NULL, 
	country VARCHAR(60) NOT NULL, 
	playing_role VARCHAR(30) NOT NULL, 
	batting_style VARCHAR(40), 
	bowling_style VARCHAR(40), 
	date_of_birth DATE, 
	PRIMARY KEY (player_id), 
	CONSTRAINT ck_players_role CHECK (playing_role IN ('Batsman','Bowler','All-rounder','Wicket-keeper'))
);

CREATE TABLE series (
	series_id INTEGER NOT NULL, 
	series_name VARCHAR(160) NOT NULL, 
	host_country VARCHAR(60) NOT NULL, 
	match_type VARCHAR(10) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE, 
	total_matches INTEGER NOT NULL, 
	PRIMARY KEY (series_id), 
	CONSTRAINT ck_series_type CHECK (match_type IN ('Test','ODI','T20I'))
);

CREATE TABLE teams (
	team_id INTEGER NOT NULL, 
	team_name VARCHAR(80) NOT NULL, 
	short_name VARCHAR(8) NOT NULL, 
	country VARCHAR(60) NOT NULL, 
	PRIMARY KEY (team_id), 
	UNIQUE (team_name)
);

CREATE TABLE venues (
	venue_id INTEGER NOT NULL, 
	venue_name VARCHAR(120) NOT NULL, 
	city VARCHAR(80) NOT NULL, 
	country VARCHAR(60) NOT NULL, 
	capacity INTEGER CHECK (capacity > 0), 
	PRIMARY KEY (venue_id), 
	UNIQUE (venue_name)
);

CREATE TABLE matches (
	match_id INTEGER NOT NULL, 
	series_id INTEGER NOT NULL, 
	description VARCHAR(200) NOT NULL, 
	match_format VARCHAR(10) NOT NULL, 
	team1_id INTEGER NOT NULL, 
	team2_id INTEGER NOT NULL, 
	venue_id INTEGER NOT NULL, 
	match_date DATE NOT NULL, 
	match_year INTEGER NOT NULL, 
	year_quarter VARCHAR(8) NOT NULL, 
	toss_winner_id INTEGER, 
	toss_decision VARCHAR(5), 
	winner_id INTEGER, 
	victory_margin INTEGER, 
	victory_type VARCHAR(8), 
	status VARCHAR(20) DEFAULT 'Completed' NOT NULL, 
	PRIMARY KEY (match_id), 
	CONSTRAINT ck_matches_format CHECK (match_format IN ('Test','ODI','T20I')), 
	CONSTRAINT ck_matches_teams CHECK (team1_id <> team2_id), 
	CONSTRAINT ck_matches_toss CHECK (toss_decision IN ('bat','bowl') OR toss_decision IS NULL), 
	CONSTRAINT ck_matches_vtype CHECK (victory_type IN ('runs','wickets') OR victory_type IS NULL), 
	FOREIGN KEY(series_id) REFERENCES series (series_id) ON DELETE CASCADE, 
	FOREIGN KEY(team1_id) REFERENCES teams (team_id), 
	FOREIGN KEY(team2_id) REFERENCES teams (team_id), 
	FOREIGN KEY(venue_id) REFERENCES venues (venue_id), 
	FOREIGN KEY(toss_winner_id) REFERENCES teams (team_id), 
	FOREIGN KEY(winner_id) REFERENCES teams (team_id)
);

CREATE INDEX ix_matches_date ON matches (match_date);

CREATE INDEX ix_matches_format_date ON matches (match_format, match_date);

CREATE INDEX ix_matches_teams ON matches (team1_id, team2_id);

CREATE INDEX ix_matches_venue ON matches (venue_id);

CREATE INDEX ix_matches_winner ON matches (winner_id);

CREATE TABLE player_career_stats (
	player_id INTEGER NOT NULL, 
	match_format VARCHAR(10) NOT NULL, 
	matches INTEGER DEFAULT '0' NOT NULL, 
	innings INTEGER DEFAULT '0' NOT NULL, 
	not_outs INTEGER DEFAULT '0' NOT NULL, 
	total_runs INTEGER DEFAULT '0' NOT NULL, 
	highest_score INTEGER DEFAULT '0' NOT NULL, 
	batting_average FLOAT, 
	strike_rate FLOAT, 
	centuries INTEGER DEFAULT '0' NOT NULL, 
	fifties INTEGER DEFAULT '0' NOT NULL, 
	total_wickets INTEGER DEFAULT '0' NOT NULL, 
	bowling_average FLOAT, 
	economy_rate FLOAT, 
	catches INTEGER DEFAULT '0' NOT NULL, 
	stumpings INTEGER DEFAULT '0' NOT NULL, 
	PRIMARY KEY (player_id, match_format), 
	FOREIGN KEY(player_id) REFERENCES players (player_id) ON DELETE CASCADE
);

CREATE INDEX ix_career_format_runs ON player_career_stats (match_format, total_runs);

CREATE TABLE batting_performances (
	perf_id INTEGER NOT NULL, 
	match_id INTEGER NOT NULL, 
	innings_no INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	team_id INTEGER NOT NULL, 
	batting_position INTEGER NOT NULL, 
	runs INTEGER NOT NULL, 
	balls_faced INTEGER NOT NULL, 
	fours INTEGER DEFAULT '0' NOT NULL, 
	sixes INTEGER DEFAULT '0' NOT NULL, 
	strike_rate FLOAT, 
	is_out INTEGER DEFAULT '1' NOT NULL, 
	PRIMARY KEY (perf_id), 
	CONSTRAINT uq_bat_match_inn_player UNIQUE (match_id, innings_no, player_id), 
	CONSTRAINT ck_bat_nonneg CHECK (runs >= 0 AND balls_faced >= 0), 
	FOREIGN KEY(match_id) REFERENCES matches (match_id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (player_id), 
	FOREIGN KEY(team_id) REFERENCES teams (team_id)
);

CREATE INDEX ix_bat_match_inn_pos ON batting_performances (match_id, innings_no, batting_position);

CREATE INDEX ix_bat_player ON batting_performances (player_id);

CREATE TABLE bowling_performances (
	perf_id INTEGER NOT NULL, 
	match_id INTEGER NOT NULL, 
	innings_no INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	team_id INTEGER NOT NULL, 
	legal_balls INTEGER NOT NULL, 
	maidens INTEGER DEFAULT '0' NOT NULL, 
	runs_conceded INTEGER NOT NULL, 
	wickets INTEGER NOT NULL, 
	economy FLOAT, 
	PRIMARY KEY (perf_id), 
	CONSTRAINT uq_bowl_match_inn_player UNIQUE (match_id, innings_no, player_id), 
	CONSTRAINT ck_bowl_balls CHECK (legal_balls > 0), 
	FOREIGN KEY(match_id) REFERENCES matches (match_id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (player_id), 
	FOREIGN KEY(team_id) REFERENCES teams (team_id)
);

CREATE INDEX ix_bowl_match ON bowling_performances (match_id);

CREATE INDEX ix_bowl_player ON bowling_performances (player_id);

CREATE TABLE fielding_performances (
	match_id INTEGER NOT NULL, 
	player_id INTEGER NOT NULL, 
	catches INTEGER DEFAULT '0' NOT NULL, 
	stumpings INTEGER DEFAULT '0' NOT NULL, 
	PRIMARY KEY (match_id, player_id), 
	FOREIGN KEY(match_id) REFERENCES matches (match_id) ON DELETE CASCADE, 
	FOREIGN KEY(player_id) REFERENCES players (player_id)
);

CREATE VIEW v_match_results AS SELECT m.match_id, m.match_date, m.match_format, m.description, t1.team_name AS team1, t2.team_name AS team2, w.team_name AS winner, m.victory_margin, m.victory_type, v.venue_name, v.city, v.country AS venue_country FROM matches m JOIN teams t1 ON t1.team_id = m.team1_id JOIN teams t2 ON t2.team_id = m.team2_id JOIN venues v ON v.venue_id = m.venue_id LEFT JOIN teams w ON w.team_id = m.winner_id;

CREATE VIEW v_player_leaderboard AS SELECT p.player_id, p.full_name, p.country, p.playing_role, SUM(c.total_runs) AS runs, SUM(c.total_wickets) AS wickets, SUM(c.matches) AS matches FROM players p JOIN player_career_stats c ON c.player_id = p.player_id GROUP BY p.player_id, p.full_name, p.country, p.playing_role;
