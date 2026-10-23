from datetime import date, timedelta

import pytest

from services import crud
from utils.db_connection import UnsafeQueryError, run_query, run_readonly, validate_readonly


def _player(**kw):
    base = dict(
        full_name="Test Player",
        country="India",
        playing_role="Batsman",
        batting_style="Right-hand bat",
        bowling_style="Does not bowl",
        date_of_birth=date(2000, 1, 1),
    )
    return {**base, **kw}


def test_player_crud_roundtrip():
    pid = crud.create_player(_player(full_name="Zed Testington"))
    assert (
        run_query("SELECT full_name FROM players WHERE player_id=:p", {"p": pid}).full_name.iloc[0]
        == "Zed Testington"
    )
    crud.update_player(
        pid,
        _player(
            full_name="Zed Testington", playing_role="All-rounder", bowling_style="Right-arm fast"
        ),
    )
    row = run_query(
        "SELECT playing_role, bowling_style FROM players WHERE player_id=:p", {"p": pid}
    ).iloc[0]
    assert (row.playing_role, row.bowling_style) == ("All-rounder", "Right-arm fast")
    crud.delete_player(pid)
    assert (
        run_query("SELECT COUNT(*) AS n FROM players WHERE player_id=:p", {"p": pid}).n.iloc[0] == 0
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"full_name": "ab"},
        {"playing_role": "Umpire"},
        {"date_of_birth": date.today() + timedelta(days=1)},
    ],
)
def test_player_validation(patch):
    with pytest.raises(crud.ValidationError):
        crud.create_player(_player(**patch))


def test_duplicate_player_rejected():
    crud.create_player(_player(full_name="Dupe Check"))
    with pytest.raises(crud.ValidationError):
        crud.create_player(_player(full_name="Dupe Check"))


def test_cannot_delete_player_with_history_without_cascade():
    pid = int(run_query("SELECT player_id FROM batting_performances LIMIT 1").player_id.iloc[0])
    with pytest.raises(crud.ValidationError):
        crud.delete_player(pid)


def test_bowling_overs_validation_and_storage():
    m = crud.match_options(1).iloc[0]
    pid = int(
        run_query(
            "SELECT player_id FROM players WHERE country = (SELECT country FROM teams WHERE team_id=:t) LIMIT 1",
            {"t": int(m.t1_id)},
        ).player_id.iloc[0]
    )
    base = dict(
        match_id=int(m.match_id),
        innings_no=4,
        player_id=pid,
        team_id=int(m.t1_id),
        maidens=0,
        runs_conceded=20,
        wickets=1,
    )
    with pytest.raises(crud.ValidationError):
        crud.create_bowling({**base, "overs": "3.7"})
    perf = crud.create_bowling({**base, "overs": "3.4"})
    stored = run_query(
        "SELECT legal_balls FROM bowling_performances WHERE perf_id=:i", {"i": perf}
    ).legal_balls.iloc[0]
    assert stored == 22
    crud.delete_bowling(perf)


def test_batting_boundaries_cannot_exceed_runs():
    m = crud.match_options(1).iloc[0]
    with pytest.raises(crud.ValidationError):
        crud.create_batting(
            dict(
                match_id=int(m.match_id),
                innings_no=4,
                player_id=1,
                team_id=int(m.t1_id),
                batting_position=3,
                runs=10,
                balls_faced=8,
                fours=3,
                sixes=0,
                is_out=True,
            )
        )


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM players",
        "SELECT 1; DROP TABLE players",
        "UPDATE players SET country='x'",
        "PRAGMA table_info(players)",
        "INSERT INTO teams VALUES (1)",
    ],
)
def test_console_rejects_writes(sql):
    with pytest.raises(UnsafeQueryError):
        validate_readonly(sql)


def test_console_runs_select_and_is_read_only():
    df, ms = run_readonly("SELECT COUNT(*) AS n FROM players")
    assert df.n.iloc[0] > 0 and ms >= 0
