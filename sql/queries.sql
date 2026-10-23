-- The 25 SQL practice questions. Replace :today, :d30, :d3y with ISO dates (e.g. '2026-10-19', '2026-09-19', '2023-10-20').

-- Q01 [Beginner] Players who represent India
-- Squad lists for commentary teams and fantasy platforms start with 'who plays for whom'.
SELECT full_name AS player, playing_role, batting_style,
       COALESCE(bowling_style, 'Does not bowl') AS bowling_style
FROM players
WHERE country = 'India'
ORDER BY playing_role, full_name;

-- Q02 [Beginner] Matches played in the last 30 days
-- Broadcasters need a rolling 'recent results' feed for pre-match shows.
SELECT m.description, t1.team_name AS team_1, t2.team_name AS team_2,
       v.venue_name, v.city, m.match_date
FROM matches m
JOIN teams  t1 ON t1.team_id  = m.team1_id
JOIN teams  t2 ON t2.team_id  = m.team2_id
JOIN venues v  ON v.venue_id  = m.venue_id
WHERE m.match_date >= :d30 AND m.match_date <= :today
ORDER BY m.match_date DESC, m.match_id DESC;

-- Q03 [Beginner] Top 10 ODI run scorers
-- Leaderboards are the most-viewed page of any cricket product.
SELECT p.full_name AS player, c.total_runs, c.batting_average, c.centuries
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE c.match_format = 'ODI'
ORDER BY c.total_runs DESC
LIMIT 10;

-- Q04 [Beginner] Stadiums with capacity above 50,000
-- Venue intelligence for ticketing, travel and broadcast planning.
SELECT venue_name, city, country, capacity
FROM venues
WHERE capacity > 50000
ORDER BY capacity DESC;

-- Q05 [Beginner] Total wins by team
-- Team strength baseline used in odds models and pre-match graphics.
SELECT t.team_name, COUNT(*) AS total_wins
FROM matches m
JOIN teams t ON t.team_id = m.winner_id
GROUP BY t.team_id, t.team_name
ORDER BY total_wins DESC;

-- Q06 [Beginner] Players per playing role
-- Squad-balance check: do we have enough keepers, all-rounders, bowlers?
SELECT playing_role AS role, COUNT(*) AS player_count
FROM players
GROUP BY playing_role
ORDER BY player_count DESC;

-- Q07 [Beginner] Highest individual score in each format
-- Records pages and 'on this day' trivia need per-format maxima.
SELECT match_format, MAX(highest_score) AS highest_score
FROM player_career_stats
GROUP BY match_format
ORDER BY highest_score DESC;

-- Q08 [Beginner] Series that started in 2024
-- Calendar planning and rights-management teams track tours by start year.
SELECT series_name, host_country, match_type, start_date, total_matches
FROM series
WHERE start_date >= '2024-01-01' AND start_date < '2025-01-01'
ORDER BY start_date;

-- Q09 [Intermediate] All-rounders with 1,000+ runs and 50+ wickets
-- Fantasy platforms pay a premium for genuine all-rounders - find them objectively.
SELECT p.full_name AS player, c.total_runs, c.total_wickets, c.match_format
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE p.playing_role = 'All-rounder'
  AND c.total_runs > 1000
  AND c.total_wickets > 50
ORDER BY c.total_runs DESC;

-- Q10 [Intermediate] Last 20 completed matches with results
-- Result tickers and 'form guide' widgets.
SELECT m.description, t1.team_name AS team_1, t2.team_name AS team_2,
       w.team_name AS winner, m.victory_margin, m.victory_type, v.venue_name
FROM matches m
JOIN teams  t1 ON t1.team_id = m.team1_id
JOIN teams  t2 ON t2.team_id = m.team2_id
JOIN teams  w  ON w.team_id  = m.winner_id
JOIN venues v  ON v.venue_id = m.venue_id
WHERE m.status = 'Completed'
ORDER BY m.match_date DESC, m.match_id DESC
LIMIT 20;

-- Q11 [Intermediate] Players compared across formats
-- Analytics firms evaluate versatility: who is elite in more than one format?
SELECT p.full_name AS player,
       SUM(CASE WHEN c.match_format = 'Test' THEN c.total_runs ELSE 0 END) AS test_runs,
       SUM(CASE WHEN c.match_format = 'ODI'  THEN c.total_runs ELSE 0 END) AS odi_runs,
       SUM(CASE WHEN c.match_format = 'T20I' THEN c.total_runs ELSE 0 END) AS t20i_runs,
       ROUND(CAST(SUM(c.total_runs) * 1.0 / NULLIF(SUM(c.innings - c.not_outs), 0) AS DECIMAL(14,4)), 2) AS overall_batting_avg
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT c.match_format) >= 2
ORDER BY SUM(c.total_runs) DESC;

-- Q12 [Intermediate] Home vs away performance by team
-- Venue-specific edges drive betting odds and tour-selection strategy.
WITH side AS (
    SELECT match_id, team1_id AS team_id, venue_id, winner_id FROM matches
    UNION ALL
    SELECT match_id, team2_id AS team_id, venue_id, winner_id FROM matches
), agg AS (
    SELECT t.team_name,
           SUM(CASE WHEN v.country =  t.country THEN 1 ELSE 0 END) AS home_played,
           SUM(CASE WHEN v.country =  t.country AND s.winner_id = s.team_id THEN 1 ELSE 0 END) AS home_wins,
           SUM(CASE WHEN v.country <> t.country THEN 1 ELSE 0 END) AS away_played,
           SUM(CASE WHEN v.country <> t.country AND s.winner_id = s.team_id THEN 1 ELSE 0 END) AS away_wins
    FROM side s
    JOIN teams  t ON t.team_id  = s.team_id
    JOIN venues v ON v.venue_id = s.venue_id
    GROUP BY t.team_id, t.team_name
)
SELECT team_name, home_played, home_wins,
       ROUND(CAST(100.0 * home_wins / NULLIF(home_played, 0) AS DECIMAL(14,4)), 2) AS home_win_pct,
       away_played, away_wins,
       ROUND(CAST(100.0 * away_wins / NULLIF(away_played, 0) AS DECIMAL(14,4)), 2) AS away_win_pct
FROM agg
ORDER BY home_wins + away_wins DESC;

-- Q13 [Intermediate] Partnerships of 100+ between consecutive batters
-- Spot the pairs that break games open - a staple of post-match analysis.
SELECT m.description, m.match_date, b1.innings_no,
       p1.full_name AS batter_1, p2.full_name AS batter_2,
       b1.batting_position AS position_1, b2.batting_position AS position_2,
       (b1.runs + b2.runs) AS combined_runs
FROM batting_performances b1
JOIN batting_performances b2
  ON  b2.match_id = b1.match_id
  AND b2.innings_no = b1.innings_no
  AND b2.batting_position = b1.batting_position + 1
JOIN players p1 ON p1.player_id = b1.player_id
JOIN players p2 ON p2.player_id = b2.player_id
JOIN matches m  ON m.match_id  = b1.match_id
WHERE b1.runs + b2.runs >= 100
ORDER BY combined_runs DESC;

-- Q14 [Intermediate] Bowling performance by venue
-- Venue-specific bowler form is gold for fantasy captain picks.
WITH per_match AS (
    SELECT w.player_id, m.venue_id, w.match_id,
           SUM(w.legal_balls) AS balls, SUM(w.runs_conceded) AS runs, SUM(w.wickets) AS wkts
    FROM bowling_performances w
    JOIN matches m ON m.match_id = w.match_id
    GROUP BY w.player_id, m.venue_id, w.match_id
    HAVING SUM(w.legal_balls) >= 24
)
SELECT p.full_name AS bowler, v.venue_name, COUNT(*) AS matches_played,
       ROUND(CAST(AVG(pm.runs * 6.0 / pm.balls) AS DECIMAL(14,4)), 2) AS avg_economy,
       SUM(pm.wkts) AS total_wickets
FROM per_match pm
JOIN players p ON p.player_id = pm.player_id
JOIN venues  v ON v.venue_id  = pm.venue_id
GROUP BY p.player_id, p.full_name, v.venue_id, v.venue_name
HAVING COUNT(*) >= 3
ORDER BY avg_economy ASC;

-- Q15 [Intermediate] Players who thrive in close matches
-- Clutch performance: who delivers when the margin is tiny?
WITH close_matches AS (
    SELECT match_id, winner_id FROM matches
    WHERE winner_id IS NOT NULL
      AND ((victory_type = 'runs' AND victory_margin < 50)
        OR (victory_type = 'wickets' AND victory_margin < 5))
)
SELECT p.full_name AS player,
       COUNT(DISTINCT b.match_id) AS close_matches_played,
       ROUND(CAST(AVG(b.runs * 1.0) AS DECIMAL(14,4)), 2) AS avg_runs,
       COUNT(DISTINCT CASE WHEN b.team_id = cm.winner_id THEN b.match_id END) AS team_won_when_batted
FROM batting_performances b
JOIN close_matches cm ON cm.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
GROUP BY p.player_id, p.full_name
ORDER BY avg_runs DESC;

-- Q16 [Intermediate] Year-by-year batting trend since 2020
-- Spot rising and falling stars with a yearly lens.
SELECT p.full_name AS player, m.match_year,
       COUNT(DISTINCT m.match_id) AS matches_played,
       ROUND(CAST(SUM(b.runs) * 1.0 / COUNT(DISTINCT m.match_id) AS DECIMAL(14,4)), 2) AS avg_runs_per_match,
       ROUND(CAST(AVG(b.strike_rate) AS DECIMAL(14,4)), 2) AS avg_strike_rate
FROM batting_performances b
JOIN matches m ON m.match_id  = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2020-01-01'
GROUP BY p.player_id, p.full_name, m.match_year
HAVING COUNT(DISTINCT m.match_id) >= 5
ORDER BY p.full_name, m.match_year;

-- Q17 [Advanced] Does winning the toss win the match?
-- A classic betting-market question - quantify the toss advantage by decision.
SELECT toss_decision AS toss_decision,
       COUNT(*) AS matches,
       SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) AS toss_winner_won,
       ROUND(CAST(100.0 * SUM(CASE WHEN toss_winner_id = winner_id THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(14,4)), 2) AS win_pct
FROM matches
WHERE winner_id IS NOT NULL AND toss_winner_id IS NOT NULL
GROUP BY toss_decision;

-- Q18 [Advanced] Most economical limited-overs bowlers
-- Death-over and powerplay specialists are priced by economy; find the real ones.
WITH per_match AS (
    SELECT w.player_id, w.match_id, SUM(w.legal_balls) AS balls,
           SUM(w.runs_conceded) AS runs, SUM(w.wickets) AS wkts
    FROM bowling_performances w
    JOIN matches m ON m.match_id = w.match_id
    WHERE m.match_format IN ('ODI', 'T20I')
    GROUP BY w.player_id, w.match_id
)
SELECT p.full_name AS bowler, COUNT(*) AS matches_bowled,
       SUM(pm.balls) AS total_balls,
       ROUND(CAST(SUM(pm.runs) * 6.0 / SUM(pm.balls) AS DECIMAL(14,4)), 2) AS economy_rate,
       SUM(pm.wkts) AS total_wickets
FROM per_match pm
JOIN players p ON p.player_id = pm.player_id
GROUP BY p.player_id, p.full_name
HAVING COUNT(*) >= 10 AND SUM(pm.balls) * 1.0 / COUNT(*) >= 12
ORDER BY economy_rate ASC;

-- Q19 [Advanced] Most consistent batters since 2022
-- Low variance = reliable. Fantasy and selection panels both want this.
SELECT p.full_name AS player, COUNT(*) AS innings,
       ROUND(CAST(AVG(b.runs * 1.0) AS DECIMAL(14,4)), 2) AS avg_runs,
       ROUND(CAST(SQRT(AVG(b.runs * b.runs * 1.0) - AVG(b.runs * 1.0) * AVG(b.runs * 1.0)) AS DECIMAL(14,4)), 2) AS std_dev_runs
FROM batting_performances b
JOIN matches m ON m.match_id  = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= '2022-01-01' AND b.balls_faced >= 10
GROUP BY p.player_id, p.full_name
ORDER BY std_dev_runs ASC;

-- Q20 [Advanced] Matches played and batting average by format
-- One row per player: workload and quality in every format.
SELECT p.full_name AS player,
       SUM(CASE WHEN c.match_format = 'Test' THEN c.matches ELSE 0 END) AS test_matches,
       SUM(CASE WHEN c.match_format = 'ODI'  THEN c.matches ELSE 0 END) AS odi_matches,
       SUM(CASE WHEN c.match_format = 'T20I' THEN c.matches ELSE 0 END) AS t20i_matches,
       MAX(CASE WHEN c.match_format = 'Test' THEN c.batting_average END) AS test_avg,
       MAX(CASE WHEN c.match_format = 'ODI'  THEN c.batting_average END) AS odi_avg,
       MAX(CASE WHEN c.match_format = 'T20I' THEN c.batting_average END) AS t20i_avg,
       SUM(c.matches) AS total_matches
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
GROUP BY p.player_id, p.full_name
HAVING SUM(c.matches) >= 20
ORDER BY total_matches DESC;

-- Q21 [Advanced] Weighted all-round performance ranking (per format)
-- A single 'impact score' blending batting, bowling and fielding.
WITH scored AS (
    SELECT p.full_name AS player, p.country, c.match_format,
           (c.total_runs * 0.01 + COALESCE(c.batting_average, 0) * 0.5 + COALESCE(c.strike_rate, 0) * 0.3) AS batting_pts,
           CASE WHEN c.total_wickets > 0
                THEN c.total_wickets * 2 + (50 - c.bowling_average) * 0.5 + (6 - c.economy_rate) * 2
                ELSE 0 END AS bowling_pts,
           (c.catches * 3 + c.stumpings * 5) AS fielding_pts
    FROM player_career_stats c
    JOIN players p ON p.player_id = c.player_id
), ranked AS (
    SELECT *, batting_pts + bowling_pts + fielding_pts AS total_pts,
           ROW_NUMBER() OVER (PARTITION BY match_format
                              ORDER BY batting_pts + bowling_pts + fielding_pts DESC) AS format_rank
    FROM scored
)
SELECT match_format, format_rank, player, country,
       ROUND(CAST(batting_pts AS DECIMAL(14,4)), 2) AS batting_pts, ROUND(CAST(bowling_pts AS DECIMAL(14,4)), 2) AS bowling_pts,
       ROUND(CAST(fielding_pts AS DECIMAL(14,4)), 2) AS fielding_pts, ROUND(CAST(total_pts AS DECIMAL(14,4)), 2) AS total_pts
FROM ranked
ORDER BY match_format, format_rank;

-- Q22 [Advanced] Head-to-head analysis (pairs with 5+ matches, last 3 years)
-- Pre-match previews: who has the edge, and does batting first matter?
WITH h AS (
    SELECT m.match_id, m.venue_id, m.winner_id, m.victory_type, m.victory_margin,
           CASE WHEN m.team1_id < m.team2_id THEN m.team1_id ELSE m.team2_id END AS team_a,
           CASE WHEN m.team1_id < m.team2_id THEN m.team2_id ELSE m.team1_id END AS team_b,
           CASE WHEN m.toss_decision = 'bat' THEN m.toss_winner_id
                WHEN m.toss_winner_id = m.team1_id THEN m.team2_id ELSE m.team1_id END AS bat_first
    FROM matches m
    WHERE m.match_date >= :d3y AND m.winner_id IS NOT NULL
), agg AS (
    SELECT team_a, team_b, COUNT(*) AS matches,
           SUM(CASE WHEN winner_id = team_a THEN 1 ELSE 0 END) AS wins_a,
           SUM(CASE WHEN winner_id = team_b THEN 1 ELSE 0 END) AS wins_b,
           AVG(CASE WHEN winner_id = team_a AND victory_type = 'runs'    THEN victory_margin * 1.0 END) AS a_run_margin,
           AVG(CASE WHEN winner_id = team_a AND victory_type = 'wickets' THEN victory_margin * 1.0 END) AS a_wkt_margin,
           AVG(CASE WHEN winner_id = team_b AND victory_type = 'runs'    THEN victory_margin * 1.0 END) AS b_run_margin,
           AVG(CASE WHEN winner_id = team_b AND victory_type = 'wickets' THEN victory_margin * 1.0 END) AS b_wkt_margin,
           SUM(CASE WHEN winner_id = team_a AND bat_first = team_a THEN 1 ELSE 0 END) AS a_wins_batting_first,
           SUM(CASE WHEN winner_id = team_a AND bat_first = team_b THEN 1 ELSE 0 END) AS a_wins_bowling_first,
           SUM(CASE WHEN winner_id = team_b AND bat_first = team_b THEN 1 ELSE 0 END) AS b_wins_batting_first,
           SUM(CASE WHEN winner_id = team_b AND bat_first = team_a THEN 1 ELSE 0 END) AS b_wins_bowling_first,
           COUNT(DISTINCT venue_id) AS venues_used
    FROM h
    GROUP BY team_a, team_b
    HAVING COUNT(*) >= 5
)
SELECT ta.team_name AS team_a, tb.team_name AS team_b, matches, wins_a, wins_b,
       ROUND(CAST(100.0 * wins_a / matches AS DECIMAL(14,4)), 2) AS win_pct_a, ROUND(CAST(100.0 * wins_b / matches AS DECIMAL(14,4)), 2) AS win_pct_b,
       ROUND(CAST(a_run_margin AS DECIMAL(14,4)), 2) AS a_avg_runs_margin, ROUND(CAST(a_wkt_margin AS DECIMAL(14,4)), 2) AS a_avg_wkts_margin,
       ROUND(CAST(b_run_margin AS DECIMAL(14,4)), 2) AS b_avg_runs_margin, ROUND(CAST(b_wkt_margin AS DECIMAL(14,4)), 2) AS b_avg_wkts_margin,
       a_wins_batting_first, a_wins_bowling_first, b_wins_batting_first, b_wins_bowling_first, venues_used
FROM agg
JOIN teams ta ON ta.team_id = agg.team_a
JOIN teams tb ON tb.team_id = agg.team_b
ORDER BY matches DESC, ta.team_name;

-- Q23 [Advanced] Player form & momentum (last 10 innings)
-- Form labels power fantasy captain suggestions and pundit graphics.
WITH ranked AS (
    SELECT b.player_id, b.runs, b.strike_rate,
           ROW_NUMBER() OVER (PARTITION BY b.player_id ORDER BY m.match_date DESC, b.perf_id DESC) AS rn
    FROM batting_performances b
    JOIN matches m ON m.match_id = b.match_id
), agg AS (
    SELECT player_id,
           AVG(CASE WHEN rn <= 5 THEN runs * 1.0 END)  AS avg_last5,
           AVG(runs * 1.0)                              AS avg_last10,
           AVG(CASE WHEN rn <= 5 THEN strike_rate END)  AS sr_last5,
           AVG(CASE WHEN rn >  5 THEN strike_rate END)  AS sr_prev5,
           SUM(CASE WHEN runs > 50 THEN 1 ELSE 0 END)   AS scores_above_50,
           SQRT(AVG(runs * runs * 1.0) - AVG(runs * 1.0) * AVG(runs * 1.0)) AS std_dev
    FROM ranked WHERE rn <= 10
    GROUP BY player_id
), scored AS (
    SELECT *, 0.5 * avg_last5 + 0.3 * avg_last10 + 3 * scores_above_50 - 0.1 * std_dev AS form_score FROM agg
)
SELECT p.full_name AS player, p.country,
       ROUND(CAST(avg_last5 AS DECIMAL(14,4)), 2) AS avg_last5, ROUND(CAST(avg_last10 AS DECIMAL(14,4)), 2) AS avg_last10,
       ROUND(CAST(sr_last5 AS DECIMAL(14,4)), 2) AS sr_last5, ROUND(CAST(sr_prev5 AS DECIMAL(14,4)), 2) AS sr_prev5,
       CASE WHEN sr_last5 > sr_prev5 THEN 'Rising' ELSE 'Falling' END AS sr_trend,
       scores_above_50, ROUND(CAST(std_dev AS DECIMAL(14,4)), 2) AS consistency_sd, ROUND(CAST(form_score AS DECIMAL(14,4)), 2) AS form_score,
       CASE WHEN form_score >= 32 THEN 'Excellent Form'
            WHEN form_score >= 22 THEN 'Good Form'
            WHEN form_score >= 12 THEN 'Average Form'
            ELSE 'Poor Form' END AS form_category
FROM scored
JOIN players p ON p.player_id = scored.player_id
ORDER BY form_score DESC;

-- Q24 [Advanced] Best batting partnerships (consecutive positions, 5+ together)
-- Which pairings are worth keeping together at the top of the order?
WITH part AS (
    SELECT b1.player_id AS p1, b2.player_id AS p2, (b1.runs + b2.runs) AS pr
    FROM batting_performances b1
    JOIN batting_performances b2
      ON  b2.match_id = b1.match_id AND b2.innings_no = b1.innings_no
      AND b2.batting_position = b1.batting_position + 1
)
SELECT pl1.full_name AS batter_1, pl2.full_name AS batter_2,
       COUNT(*) AS partnerships,
       ROUND(CAST(AVG(pr * 1.0) AS DECIMAL(14,4)), 2) AS avg_partnership,
       SUM(CASE WHEN pr > 50 THEN 1 ELSE 0 END) AS over_50,
       MAX(pr) AS highest,
       ROUND(CAST(100.0 * SUM(CASE WHEN pr > 50 THEN 1 ELSE 0 END) / COUNT(*) AS DECIMAL(14,4)), 2) AS success_rate_pct
FROM part
JOIN players pl1 ON pl1.player_id = part.p1
JOIN players pl2 ON pl2.player_id = part.p2
GROUP BY part.p1, part.p2, pl1.full_name, pl2.full_name
HAVING COUNT(*) >= 5
ORDER BY success_rate_pct DESC, avg_partnership DESC;

-- Q25 [Advanced] Quarterly performance evolution & career phase
-- Is a player ascending, declining or plateauing? Selection panels need the trend, not a snapshot.
WITH q AS (
    SELECT b.player_id, m.year_quarter, COUNT(DISTINCT m.match_id) AS matches,
           AVG(b.runs * 1.0) AS avg_runs, AVG(b.strike_rate) AS avg_sr
    FROM batting_performances b
    JOIN matches m ON m.match_id = b.match_id
    WHERE m.match_date >= :d3y
    GROUP BY b.player_id, m.year_quarter
    HAVING COUNT(DISTINCT m.match_id) >= 3
), t AS (
    SELECT player_id, year_quarter, avg_runs, avg_sr,
           LAG(avg_runs) OVER (PARTITION BY player_id ORDER BY year_quarter) AS prev_runs,
           ROW_NUMBER()  OVER (PARTITION BY player_id ORDER BY year_quarter)  AS qn,
           COUNT(*)      OVER (PARTITION BY player_id)                        AS nq
    FROM q
), s AS (
    SELECT player_id, MAX(nq) AS quarters,
           AVG(CASE WHEN qn <= 3 THEN avg_runs END)      AS early_avg,
           AVG(CASE WHEN qn > nq - 3 THEN avg_runs END)  AS recent_avg,
           AVG(CASE WHEN qn > nq - 3 THEN avg_sr END)    AS recent_sr,
           AVG(avg_runs - prev_runs)                      AS avg_qoq_change,
           SUM(CASE WHEN avg_runs > prev_runs THEN 1 ELSE 0 END) AS improving_quarters,
           SUM(CASE WHEN avg_runs < prev_runs THEN 1 ELSE 0 END) AS declining_quarters
    FROM t
    GROUP BY player_id
    HAVING MAX(nq) >= 6
)
SELECT p.full_name AS player, quarters,
       ROUND(CAST(early_avg AS DECIMAL(14,4)), 2) AS first_3q_avg, ROUND(CAST(recent_avg AS DECIMAL(14,4)), 2) AS last_3q_avg,
       ROUND(CAST(recent_sr AS DECIMAL(14,4)), 2) AS recent_strike_rate, ROUND(CAST(avg_qoq_change AS DECIMAL(14,4)), 2) AS avg_qoq_change,
       improving_quarters, declining_quarters,
       CASE WHEN recent_avg > early_avg * 1.10 THEN 'Career Ascending'
            WHEN recent_avg < early_avg * 0.90 THEN 'Career Declining'
            ELSE 'Career Stable' END AS career_phase
FROM s
JOIN players p ON p.player_id = s.player_id
ORDER BY (recent_avg - early_avg) DESC;
