"""Synthetic-but-realistic cricket data generator.

IMPORTANT: every player name and statistic produced here is FICTIONAL demo data so the
25 SQL questions have rich rows to analyse without needing an API quota. Live pages use
the real Cricbuzz API; `scripts/sync_from_api.py` can load real data into the same schema.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import insert, text
from sqlalchemy.engine import Engine

from database import models as m

TEAMS = [  # name, short, country, strength
    ("India", "IND", "India", 1.12),
    ("Australia", "AUS", "Australia", 1.10),
    ("England", "ENG", "England", 1.05),
    ("South Africa", "SA", "South Africa", 1.03),
    ("New Zealand", "NZ", "New Zealand", 1.02),
    ("Pakistan", "PAK", "Pakistan", 1.00),
    ("Sri Lanka", "SL", "Sri Lanka", 0.93),
    ("Afghanistan", "AFG", "Afghanistan", 0.92),
    ("West Indies", "WI", "West Indies", 0.90),
    ("Bangladesh", "BAN", "Bangladesh", 0.88),
]

VENUES = [  # name, city, country, capacity
    ("Narendra Modi Stadium", "Ahmedabad", "India", 132000),
    ("Eden Gardens", "Kolkata", "India", 68000),
    ("MA Chidambaram Stadium", "Chennai", "India", 50000),
    ("M. Chinnaswamy Stadium", "Bengaluru", "India", 40000),
    ("Wankhede Stadium", "Mumbai", "India", 33100),
    ("Arun Jaitley Stadium", "Delhi", "India", 35000),
    ("Melbourne Cricket Ground", "Melbourne", "Australia", 100024),
    ("Optus Stadium", "Perth", "Australia", 60000),
    ("Sydney Cricket Ground", "Sydney", "Australia", 48000),
    ("The Gabba", "Brisbane", "Australia", 42000),
    ("Lord's", "London", "England", 31100),
    ("The Oval", "London", "England", 27500),
    ("Old Trafford", "Manchester", "England", 26000),
    ("Edgbaston", "Birmingham", "England", 25000),
    ("Gaddafi Stadium", "Lahore", "Pakistan", 34000),
    ("National Stadium", "Karachi", "Pakistan", 34228),
    ("Wanderers Stadium", "Johannesburg", "South Africa", 34000),
    ("Newlands", "Cape Town", "South Africa", 25000),
    ("SuperSport Park", "Centurion", "South Africa", 22000),
    ("Eden Park", "Auckland", "New Zealand", 50000),
    ("Hagley Oval", "Christchurch", "New Zealand", 18000),
    ("Basin Reserve", "Wellington", "New Zealand", 11600),
    ("R. Premadasa Stadium", "Colombo", "Sri Lanka", 35000),
    ("Galle International Stadium", "Galle", "Sri Lanka", 35000),
    ("Shere Bangla National Stadium", "Dhaka", "Bangladesh", 26000),
    ("Zohur Ahmed Chowdhury Stadium", "Chattogram", "Bangladesh", 20000),
    ("Kensington Oval", "Bridgetown", "West Indies", 28000),
    ("Sabina Park", "Kingston", "West Indies", 20000),
    ("Providence Stadium", "Georgetown", "West Indies", 15000),
    ("Dubai International Stadium", "Dubai", "United Arab Emirates", 25000),
    ("Sheikh Zayed Stadium", "Abu Dhabi", "United Arab Emirates", 20000),
    ("Sharjah Cricket Stadium", "Sharjah", "United Arab Emirates", 16000),
]

NAMES = {  # country -> (first names, surnames)  - all fictional combinations
    "India": (
        "Aarav Vihaan Kabir Arjun Ishaan Rohan Aditya Dhruv Karan Nikhil Siddharth Tanmay Yash Harsh Pranav Rahul Mohit Varun Neel Ayush",
        "Mehta Iyer Nair Reddy Kulkarni Patel Menon Rao Bhatt Chauhan Desai Joshi Malhotra Pillai Saxena Thakur Kapoor Bose Naidu Shetty",
    ),
    "Australia": (
        "Jack Liam Noah Ethan Mitchell Cameron Lachlan Hayden Riley Tom Callum Brodie Flynn Archer Heath Jarrod Dylan Corey Nate Zane",
        "Hartley Brennan Callaghan Whitlock Pearce Sinclair Fraser Mercer Donovan Ridley Kingston Gallagher Thornton Hargreaves Mackay Dalton Prescott Rowe Stanton Wells",
    ),
    "England": (
        "Oliver Harry George Charlie Jacob Thomas Archie Freddie Joe Ben Will Luke Reece Toby Alfie Rory Jamie Nathan Callan Max",
        "Pemberton Ashcroft Caldwell Fenwick Harcourt Lockwood Marlow Netherton Radcliffe Stanhope Thistlewood Winslow Yardley Bellamy Carrington Danvers Ellerby Foxley Gresham Holloway",
    ),
    "South Africa": (
        "Pieter Johan Willem Dewald Ruan Hennie Jaco Kobus Riaan Stefan Wian Theo Zander Brandon Cobus Gerhard Tiaan Reinhardt Dane Elton",
        "Botha Pretorius Kruger Nel Joubert Marais Venter Coetzee Swanepoel Lombard Visser Oosthuizen Fourie Bezuidenhout Engelbrecht Hattingh Terblanche Mostert Jansen Rossouw",
    ),
    "New Zealand": (
        "Finn Hamish Tane Rhys Callan Brodie Jordan Mason Tama Nikau Reuben Cooper Blair Aidan Jesse Mitch Noel Scott Tyler Zac",
        "Parata Henare Ngata Tamihana Whitaker McLeod Fitzgerald Hapi Rangi Brewer Carter Dunne Eastwood Goodall Hartnett Kereama Lindsay Morrison Paewai Tipene",
    ),
    "Pakistan": (
        "Hamza Zayan Rayyan Ayaan Faisal Usman Danish Salman Bilal Saad Arslan Taimur Haris Junaid Kamran Omer Shayan Adnan Fahad Waqar",
        "Qureshi Siddiqui Chaudhry Malik Baig Lodhi Mirza Niazi Rana Sheikh Tariq Warraich Yousafzai Zaidi Abbasi Bhatti Cheema Durrani Gillani Hashmi",
    ),
    "Sri Lanka": (
        "Kasun Dilan Nuwan Chamika Sachith Lahiru Ravindu Ashen Sadeera Minod Janith Kavindu Dunith Isuru Hasitha Shehan Oshada Praveen Lakshan Mahela",
        "Fernando Perera Silva Mendis Wickramasinghe Gunaratne Jayasekara Karunathilake Liyanage Madushanka Pathirana Seneviratne Tennakoon Udawatte Weerasinghe Abeysekera Bandara Dissanayake Edirisinghe Gamage",
    ),
    "Afghanistan": (
        "Farid Naveed Hamid Sediq Wafa Zia Noor Ikram Jamal Karim Mirwais Najib Qais Sharif Waheed Aziz Bahram Fazal Gulbadin Hashim",
        "Zadran Wardak Safi Noori Karimi Mangal Stanikzai Popalzai Barakzai Kakar Durani Ahmadzai Ghazi Hotak Mohmand Niazai Sahak Tokhi Yarmal Zaman",
    ),
    "West Indies": (
        "Delroy Marlon Rashad Kirk Tyrone Jevon Omari Akeem Leon Garfield Nigel Rupert Winston Desmond Andre Darnell Jahmar Kerwin Lennox Shervin",
        "Alleyne Bishop Clarke Dacosta Forde Gittens Inniss Knight Nurse Phillips Quashie Sealy Taitt Ventour Yearwood Greaves Hinds Joseph Lashley Medford",
    ),
    "Bangladesh": (
        "Tanvir Rakib Nasir Shafiq Imtiaz Mahin Rafi Sabbir Tahmid Zubair Arafat Fahim Shahin Rubel Anik Mehedi Naim Parvez Sajid Taskin",
        "Hossain Rahman Chowdhury Sarkar Mondal Talukdar Akand Bhuiyan Das Ghosh Haque Islam Khandaker Majumder Pramanik Sikder Uddin Mollah Biswas Khan",
    ),
}
PACE = ["Right-arm fast", "Right-arm fast-medium", "Left-arm fast", "Right-arm medium"]
SPIN = ["Right-arm off-break", "Left-arm orthodox", "Right-arm leg-break", "Left-arm wrist-spin"]

LINEUP = [
    "Batsman",
    "Batsman",
    "Batsman",
    "Batsman",
    "Wicket-keeper",
    "All-rounder",
    "All-rounder",
    "Bowler",
    "Bowler",
    "Bowler",
    "Bowler",
]
RESERVES = ["Batsman", "All-rounder", "Bowler", "Bowler"]
FMT = {  # balls limit, base strike-rate, run scale, max overs/bowler, toss-bowl probability
    "T20I": dict(balls=120, sr=146, scale=0.72, maxov=4, bowl_first=0.62),
    "ODI": dict(balls=300, sr=92, scale=1.22, maxov=10, bowl_first=0.60),
    "Test": dict(balls=None, sr=52, scale=1.15, maxov=None, bowl_first=0.40),
}
ORD = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th"}


def _build_squads(rng: random.Random) -> tuple[list[dict], dict[int, list[dict]]]:
    players: list[dict] = []
    squads: dict[int, list[dict]] = {}
    used: set[str] = set()
    pid = 1
    for tid, (_, _, country, _) in enumerate(TEAMS, start=1):
        firsts, lasts = (s.split() for s in NAMES[country])
        squad = []
        for idx, role in enumerate(LINEUP + RESERVES):
            while True:
                name = f"{rng.choice(firsts)} {rng.choice(lasts)}"
                if name not in used:
                    used.add(name)
                    break
            if role == "Batsman":
                bat, bowl, style = rng.uniform(38, 50), 0.0, None
            elif role == "Wicket-keeper":
                bat, bowl, style = rng.uniform(30, 40), 0.0, None
            elif role == "All-rounder":
                bat, bowl = rng.uniform(24, 34), rng.uniform(0.8, 1.1)
                style = rng.choice(PACE + SPIN)
            else:
                bat, bowl = rng.uniform(6, 13), rng.uniform(0.9, 1.25)
                style = rng.choice(PACE + SPIN)
            p = dict(
                player_id=pid,
                full_name=name,
                country=country,
                playing_role=role,
                batting_style=rng.choice(["Right-hand bat"] * 3 + ["Left-hand bat"]),
                bowling_style=style,
                date_of_birth=date(rng.randint(1988, 2004), rng.randint(1, 12), rng.randint(1, 28)),
            )
            players.append(p)
            squad.append(
                {
                    **p,
                    "bat": bat,
                    "bowl": bowl,
                    "slot": idx + 1 if idx < 11 else None,
                    "team_id": tid,
                }
            )
            pid += 1
        squads[tid] = squad
    return players, squads


def _pick_xi(rng: random.Random, squad: list[dict]) -> list[dict]:
    """Starters with ~10% rotation from the reserves of the same role."""
    starters, reserves = squad[:11], squad[11:]
    xi: list[dict] = []
    for p in starters:
        taken = {x["player_id"] for x in xi}
        pool = [
            r
            for r in reserves
            if r["playing_role"]
            == (p["playing_role"] if p["playing_role"] != "Wicket-keeper" else "Batsman")
            and r["player_id"] not in taken
        ]
        if pool and rng.random() < 0.10:
            r = rng.choice(pool)
            xi.append({**r, "slot": p["slot"]})
        else:
            xi.append(p)
    return xi


def _innings(rng, xi, fmt, scale_adj, target=None):
    """Simulate one batting innings. Returns (rows, total, wickets, balls)."""
    cfg = FMT[fmt]
    rows, total, balls_used = [], 0, 0
    stop = False
    for pos, p in enumerate(xi, start=1):
        mean = max(p["bat"] * cfg["scale"] * scale_adj * (1.0 if pos <= 7 else 0.9), 1.5)
        runs = (
            0
            if rng.random() < 0.07
            else min(int(rng.expovariate(1.0 / mean)), {"T20I": 150, "ODI": 264}.get(fmt, 270))
        )
        aggr = rng.gauss(1.0, 0.12) * (1.1 if pos <= 2 and fmt == "T20I" else 1.0)
        balls = max(1, int(runs / (cfg["sr"] * aggr / 100.0) + rng.randint(0, 3)))
        if cfg["balls"] is not None and balls_used + balls >= cfg["balls"]:
            new_balls = max(1, cfg["balls"] - balls_used)
            runs = int(runs * new_balls / balls)
            balls, stop = new_balls, True
        if target is not None and total + runs >= target:
            runs = max(target - total, 0)
            balls = max(1, min(balls, int(runs / (cfg["sr"] / 100.0)) + 1))
            stop = True
        fours = int(runs * 0.42 / 4 * rng.uniform(0.5, 1.3))
        sixes = int(
            max(runs - fours * 4, 0) * (0.30 if fmt == "T20I" else 0.12) / 6 * rng.uniform(0.3, 1.4)
        )
        rows.append(
            dict(player=p, pos=pos, runs=runs, balls=balls, fours=fours, sixes=sixes, out=1)
        )
        total += runs
        balls_used += balls
        if stop or pos == 11:
            break
    rows[-1]["out"] = 0  # batter at the crease at the end of the innings
    if len(rows) >= 2 and len(rows) < 11 or (len(rows) == 11 and stop):
        rows[-2]["out"] = 0  # his partner is also not out
    if len(rows) == 11 and not stop:
        pass  # all out: 10 wickets, 11th batter not out
    wickets = sum(r["out"] for r in rows)
    return rows, total, wickets, balls_used


def _split_overs(rng, bowlers, n_overs, max_ov):
    weights = [
        b["bowl"] * (0.55 if b["playing_role"] == "All-rounder" else 1.0) * rng.uniform(0.8, 1.2)
        for b in bowlers
    ]
    alloc = [0] * len(bowlers)
    for _ in range(n_overs):
        cand = [i for i in range(len(bowlers)) if max_ov is None or alloc[i] < max_ov]
        if not cand:
            break
        i = rng.choices(cand, weights=[weights[j] for j in cand])[0]
        alloc[i] += 1
    return alloc


def _bowling_rows(rng, fielding_xi, total, wickets, balls, fmt):
    bowlers = [p for p in fielding_xi if p["bowl"] > 0]
    n_overs = max(1, math.ceil(balls / 6)) if FMT[fmt]["balls"] else max(30, round(total / 3.1))
    alloc = _split_overs(rng, bowlers, n_overs, FMT[fmt]["maxov"])
    bowlers_used = [(b, a) for b, a in zip(bowlers, alloc) if a > 0]
    runs_pool = max(total - int(total * 0.04), 0)
    shares = [a * rng.uniform(0.8, 1.25) / b["bowl"] for b, a in bowlers_used]
    sh_sum = sum(shares) or 1
    runs = [int(runs_pool * s / sh_sum) for s in shares]
    runs[shares.index(max(shares))] += runs_pool - sum(runs)
    wk = [0] * len(bowlers_used)
    for _ in range(wickets):
        i = rng.choices(
            range(len(bowlers_used)), weights=[a * b["bowl"] ** 2 for b, a in bowlers_used]
        )[0]
        wk[i] += 1
    out = []
    for (b, a), r, w in zip(bowlers_used, runs, wk):
        out.append(
            dict(
                player=b, legal_balls=a * 6, maidens=int(rng.random() * a * 0.12), runs=r, wickets=w
            )
        )
    return out


def init_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        for v in m.VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {v}"))
    m.metadata.drop_all(engine)
    m.metadata.create_all(engine)


def refresh_career_stats(engine: Engine) -> None:
    """Rebuild player_career_stats from the performance tables."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM player_career_stats"))
        bat = pd.read_sql_query(
            text(
                "SELECT b.player_id, mt.match_format, b.runs, b.balls_faced, b.is_out FROM batting_performances b "
                "JOIN matches mt ON mt.match_id = b.match_id"
            ),
            conn,
        )
        bowl = pd.read_sql_query(
            text(
                "SELECT w.player_id, mt.match_format, w.legal_balls, w.runs_conceded, w.wickets FROM bowling_performances w "
                "JOIN matches mt ON mt.match_id = w.match_id"
            ),
            conn,
        )
        field = pd.read_sql_query(
            text(
                "SELECT f.player_id, mt.match_format, f.catches, f.stumpings FROM fielding_performances f "
                "JOIN matches mt ON mt.match_id = f.match_id"
            ),
            conn,
        )
        appear = pd.read_sql_query(
            text(
                "SELECT player_id, match_format, COUNT(DISTINCT match_id) AS matches FROM ("
                " SELECT b.player_id, mt.match_format, b.match_id FROM batting_performances b JOIN matches mt ON mt.match_id=b.match_id"
                " UNION SELECT w.player_id, mt.match_format, w.match_id FROM bowling_performances w JOIN matches mt ON mt.match_id=w.match_id"
                ") x GROUP BY player_id, match_format"
            ),
            conn,
        )
        keys = ["player_id", "match_format"]
        bat["dis"] = bat["is_out"]
        g = bat.groupby(keys).agg(
            innings=("runs", "size"),
            outs=("dis", "sum"),
            total_runs=("runs", "sum"),
            balls=("balls_faced", "sum"),
            highest_score=("runs", "max"),
        )
        g["centuries"] = bat[bat.runs >= 100].groupby(keys).size()
        g["fifties"] = bat[(bat.runs >= 50) & (bat.runs < 100)].groupby(keys).size()
        h = bowl.groupby(keys).agg(
            total_wickets=("wickets", "sum"),
            conceded=("runs_conceded", "sum"),
            bowled=("legal_balls", "sum"),
        )
        f = field.groupby(keys).agg(catches=("catches", "sum"), stumpings=("stumpings", "sum"))
        df = appear.set_index(keys).join([g, h, f], how="left").fillna(0).reset_index()
        df["not_outs"] = (df["innings"] - df["outs"]).astype(int)
        df["batting_average"] = (df["total_runs"] / df["outs"].where(df["outs"] > 0)).round(2)
        df["strike_rate"] = (df["total_runs"] / df["balls"].where(df["balls"] > 0) * 100).round(2)
        df["bowling_average"] = (
            df["conceded"] / df["total_wickets"].where(df["total_wickets"] > 0)
        ).round(2)
        df["economy_rate"] = (df["conceded"] * 6.0 / df["bowled"].where(df["bowled"] > 0)).round(2)
        cols = [
            "player_id",
            "match_format",
            "matches",
            "innings",
            "not_outs",
            "total_runs",
            "highest_score",
            "batting_average",
            "strike_rate",
            "centuries",
            "fifties",
            "total_wickets",
            "bowling_average",
            "economy_rate",
            "catches",
            "stumpings",
        ]
        out = df[cols].astype(object).where(df[cols].notna(), None)
        for c in [
            "player_id",
            "matches",
            "innings",
            "not_outs",
            "total_runs",
            "highest_score",
            "centuries",
            "fifties",
            "total_wickets",
            "catches",
            "stumpings",
        ]:
            out[c] = out[c].astype(int)
        conn.execute(insert(m.player_career_stats), out.to_dict("records"))


def seed_database(engine: Engine, seed: int = 2026, today: date | None = None) -> dict[str, int]:
    """(Re)create the schema and fill it with ~1,100 simulated international matches."""
    rng = random.Random(seed)
    today = today or date.today()
    init_schema(engine)

    teams = [
        dict(team_id=i, team_name=n, short_name=s, country=c)
        for i, (n, s, c, _) in enumerate(TEAMS, 1)
    ]
    strength = {i: st for i, (_, _, _, st) in enumerate(TEAMS, 1)}
    tmap = {t["team_id"]: t for t in teams}
    venues = [
        dict(venue_id=i, venue_name=n, city=c, country=co, capacity=cap)
        for i, (n, c, co, cap) in enumerate(VENUES, 1)
    ]
    by_country = defaultdict(list)
    for v in venues:
        by_country[v["country"]].append(v)
    players, squads = _build_squads(rng)

    series_rows, match_rows = [], []
    bat_rows, bowl_rows = [], []
    field_acc: dict[tuple[int, int], list[int]] = {}
    free = {t: date(2019, 1, 1) + timedelta(days=rng.randint(0, 40)) for t in tmap}
    mid = sid = 0
    last_day = today - timedelta(days=1)
    neutral_pairs_ok = {"Pakistan", "Afghanistan"}

    while True:
        a, b = rng.sample(list(tmap), 2)
        start = max(free[a], free[b]) + timedelta(days=rng.randint(2, 14))
        fmt = rng.choices(["Test", "ODI", "T20I"], weights=[0.18, 0.37, 0.45])[0]
        n = rng.choice([2, 3, 3, 3, 4, 5]) if fmt == "Test" else rng.choice([3, 3, 3, 4, 5])
        gap = 6 if fmt == "Test" else (3 if fmt == "ODI" else 2)
        end = start + timedelta(days=gap * (n - 1))
        if end > last_day:
            if start > last_day - timedelta(days=2):
                break
            free[a] = free[b] = end  # skip series that would finish in the future
            if all(f > last_day - timedelta(days=4) for f in free.values()):
                break
            continue
        # host selection: home of a / home of b / neutral (UAE) for teams without home grounds
        ca, cb = tmap[a]["country"], tmap[b]["country"]
        options = [c for c in (ca, cb) if c in by_country]
        host = rng.choice(
            options
            + (
                ["United Arab Emirates"]
                if (ca in neutral_pairs_ok or cb in neutral_pairs_ok)
                else []
            )
        )
        host_team = a if ca == host else (b if cb == host else None)
        tourist = b if host_team == a else a
        sid += 1
        yr = start.year
        sname = (
            f"{tmap[tourist]['team_name']} tour of {host} {yr}"
            if host_team
            else f"{tmap[a]['team_name']} v {tmap[b]['team_name']} {yr} (neutral, {host})"
        )
        sname += f" - {fmt}"
        series_rows.append(
            dict(
                series_id=sid,
                series_name=sname,
                host_country=host,
                match_type=fmt,
                start_date=start,
                end_date=end,
                total_matches=n,
            )
        )
        for k in range(n):
            mid += 1
            d = start + timedelta(days=gap * k)
            venue = rng.choice(by_country[host])
            t1, t2 = (a, b) if rng.random() < 0.5 else (b, a)
            toss_w = rng.choice([t1, t2])
            decision = "bowl" if rng.random() < FMT[fmt]["bowl_first"] else "bat"
            first, second = (
                (toss_w, t2 if toss_w == t1 else t1)
                if decision == "bat"
                else ((t2 if toss_w == t1 else t1), toss_w)
            )
            xi = {t: _pick_xi(rng, squads[t]) for t in (first, second)}

            def adj(team, opp):
                home = 1.06 if tmap[team]["country"] == venue["country"] else 1.0
                return (strength[team] / strength[opp]) ** 0.7 * home

            innings_plan = [(first, second), (second, first)] + (
                [(first, second), (second, first)] if fmt == "Test" else []
            )
            totals = {first: 0, second: 0}
            inn_results = []
            for ino, (bt, fl) in enumerate(innings_plan, start=1):
                target = None
                if fmt != "Test" and ino == 2:
                    target = totals[first] + 1
                if fmt == "Test" and ino == 4:
                    target = totals[first] - totals[second] + 1
                rows, tot, wk, balls = _innings(rng, xi[bt], fmt, adj(bt, fl), target)
                if fmt != "Test" and ino == 2 and tot == totals[first]:  # avoid ties
                    rows[-1]["runs"] += 1
                    tot += 1
                totals[bt] += tot
                inn_results.append((ino, bt, fl, rows, tot, wk, balls))
            winner = margin = vtype = None
            if fmt == "Test":
                wk4 = inn_results[3][5]
                if totals[second] > totals[first]:
                    winner, vtype, margin = second, "wickets", max(10 - wk4, 1)
                else:
                    winner, vtype, margin = first, "runs", max(totals[first] - totals[second], 1)
            else:
                if totals[second] > totals[first]:
                    winner, vtype, margin = second, "wickets", max(10 - inn_results[1][5], 1)
                else:
                    winner, vtype, margin = first, "runs", max(totals[first] - totals[second], 1)
            qn = (d.month - 1) // 3 + 1
            match_rows.append(
                dict(
                    match_id=mid,
                    series_id=sid,
                    description=f"{tmap[t1]['short_name']} vs {tmap[t2]['short_name']}, {ORD[k + 1]} {fmt}",
                    match_format=fmt,
                    team1_id=t1,
                    team2_id=t2,
                    venue_id=venue["venue_id"],
                    match_date=d,
                    match_year=d.year,
                    year_quarter=f"{d.year}-Q{qn}",
                    toss_winner_id=toss_w,
                    toss_decision=decision,
                    winner_id=winner,
                    victory_margin=margin,
                    victory_type=vtype,
                    status="Completed",
                )
            )
            for ino, bt, fl, rows, tot, wk, balls in inn_results:
                for r in rows:
                    p = r["player"]
                    bat_rows.append(
                        dict(
                            match_id=mid,
                            innings_no=ino,
                            player_id=p["player_id"],
                            team_id=bt,
                            batting_position=r["pos"],
                            runs=r["runs"],
                            balls_faced=r["balls"],
                            fours=r["fours"],
                            sixes=r["sixes"],
                            strike_rate=round(r["runs"] / r["balls"] * 100, 2),
                            is_out=r["out"],
                        )
                    )
                for br in _bowling_rows(rng, xi[fl], tot, wk, balls, fmt):
                    p = br["player"]
                    bowl_rows.append(
                        dict(
                            match_id=mid,
                            innings_no=ino,
                            player_id=p["player_id"],
                            team_id=fl,
                            legal_balls=br["legal_balls"],
                            maidens=br["maidens"],
                            runs_conceded=br["runs"],
                            wickets=br["wickets"],
                            economy=round(br["runs"] * 6.0 / br["legal_balls"], 2),
                        )
                    )
                fielders = xi[fl]
                wts = [2 if f["playing_role"] == "Wicket-keeper" else 1 for f in fielders]
                for r in rows:
                    if not r["out"]:
                        continue
                    x = rng.random()
                    if x < 0.62:
                        f = rng.choices(fielders, weights=wts)[0]
                        field_acc.setdefault((mid, f["player_id"]), [0, 0])[0] += 1
                    elif x < 0.69:
                        keepers = [f for f in fielders if f["playing_role"] == "Wicket-keeper"]
                        if keepers:
                            field_acc.setdefault((mid, keepers[0]["player_id"]), [0, 0])[1] += 1
        free[a] = free[b] = end

    field_rows = [
        dict(match_id=k[0], player_id=k[1], catches=v[0], stumpings=v[1])
        for k, v in field_acc.items()
    ]
    with engine.begin() as conn:
        for table, rows in [
            (m.teams, teams),
            (m.venues, venues),
            (m.players, players),
            (m.series, series_rows),
            (m.matches, match_rows),
            (m.batting_performances, bat_rows),
            (m.bowling_performances, bowl_rows),
            (m.fielding_performances, field_rows),
        ]:
            for i in range(0, len(rows), 5000):
                conn.execute(insert(table), rows[i : i + 5000])
    refresh_career_stats(engine)
    with engine.begin() as conn:
        for name, body in m.VIEWS.items():
            conn.execute(text(f"CREATE VIEW {name} AS {body}"))
    return dict(
        teams=len(teams),
        venues=len(venues),
        players=len(players),
        series=len(series_rows),
        matches=len(match_rows),
        batting=len(bat_rows),
        bowling=len(bowl_rows),
        fielding=len(field_rows),
    )
