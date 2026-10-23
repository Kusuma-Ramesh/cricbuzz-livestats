"""Regression tests for the two Stat Arcade feedback bugs.

Bug 1 (Guess the Total): the feedback never stated the guess it had graded, so it was read against the
next round's slider ("guess 200, actual 154, 14 off").
Bug 2 (Higher or Lower): stale feedback naming one player of the previous pair was shown under the new pair.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from services import arcade

PAGE = str(Path(__file__).resolve().parents[1] / "pages" / "stat_arcade.py")


def open_page() -> AppTest:
    at = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not at.exception, at.exception
    return at


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


# ------------------------------------------------------------------ pure helpers: Guess the Total
@pytest.mark.parametrize(
    "guess,actual,err,pts",
    [
        (200, 154, 46, 4),
        (154, 200, 46, 4),
        (140, 154, 14, 36),
        (154, 154, 0, 50),
        (40, 154, 114, 0),
    ],
)
def test_difference_is_absolute_and_xp_follows_it(guess, actual, err, pts):
    r = arcade.grade_total_guess(guess, actual)
    assert r == {"guess": guess, "actual": actual, "err": err, "pts": pts}


def test_feedback_states_every_number_it_was_graded_on():
    r = arcade.grade_total_guess(200, 154)
    text = arcade.total_feedback("Team A v Team B, 2nd ODI", r)
    for expected in (
        "Team A v Team B, 2nd ODI",
        "you guessed 200",
        "actual total was 154",
        "46 off",
        "+4 XP",
    ):
        assert expected in text
    assert "14 off" not in text


# ------------------------------------------------------------------ pure helpers: Higher or Lower
@pytest.mark.parametrize(
    "runs_a,runs_b,guess,right",
    [
        (100, 324, "higher", True),
        (100, 324, "lower", False),
        (324, 100, "lower", True),
        (324, 100, "higher", False),
        (200, 200, "higher", True),
        (200, 200, "lower", False),
    ],
)
def test_higher_lower_grading(runs_a, runs_b, guess, right):
    assert arcade.grade_higher_lower(runs_a, runs_b, guess) is right


def test_higher_lower_feedback_names_both_players_and_the_guess():
    pa = {"full_name": "Nathan Yardley", "runs": 324}
    pb = {"full_name": "Mitch Morrison", "runs": 1234}
    text = arcade.higher_lower_feedback(pa, pb, "lower", False, 0)
    for expected in (
        "Nathan Yardley 324 runs",
        "Mitch Morrison 1,234 runs",
        "you said lower",
        "Not quite",
    ):
        assert expected in text
    assert "+10 XP" in arcade.higher_lower_feedback(pa, pb, "higher", True, 10)


# ------------------------------------------------------------------ page: Guess the Total (bug 1)
@pytest.mark.parametrize(
    "guess,err,pts", [(200, 46, 4), (140, 14, 36), (154, 0, 50), (400, 246, 0)]
)
def test_total_feedback_on_the_page_matches_the_graded_round(guess, err, pts):
    at = open_page()
    at.session_state["gt"] = {
        "match_id": 999001,
        "description": "Regression XI v Test XI, 1st ODI",
        "match_format": "ODI",
        "total": 154,
    }
    at.run()
    assert at.slider[0].key == "gt_guess_999001"
    at.slider[0].set_value(guess)
    button(at, "Lock it in").click().run()
    assert not at.exception, at.exception

    text = next(i.value for i in at.info if "Regression XI" in i.value)
    assert f"you guessed {guess}" in text and "actual total was 154" in text
    assert f"{err} off" in text and f"+{pts} XP" in text
    assert at.session_state["xp"] == pts  # XP awarded == XP printed

    # the NEW round shows its own fresh slider at its own default, never the previous guess
    new = at.session_state["gt"]
    assert new["match_id"] != 999001
    assert at.slider[0].key == f"gt_guess_{int(new['match_id'])}"
    assert at.slider[0].value == (280 if new["match_format"] == "T20I" else 400) // 2


def test_total_feedback_is_shown_above_the_new_question():
    at = open_page()
    at.session_state["gt"] = {
        "match_id": 999002,
        "description": "Order Check, 1st T20I",
        "match_format": "T20I",
        "total": 150,
    }
    at.run()
    button(at, "Lock it in").click().run()
    game = next(c for c in at.columns if any(k.type == "slider" for k in c.children.values()))
    kinds = [(k.type, getattr(k, "value", "")) for k in game.children.values()]
    info_at = next(i for i, (t, v) in enumerate(kinds) if "Last round" in str(v))
    question_at = next(i for i, (t, v) in enumerate(kinds) if "first-innings total?" in str(v))
    assert info_at < question_at


# ------------------------------------------------------------------ page: Higher or Lower (bug 2)
def test_higher_lower_feedback_describes_the_round_that_was_answered():
    at = open_page()
    pa = {"full_name": "Nathan Yardley", "country": "England", "runs": 324}
    pb = {"full_name": "Previous Rival", "country": "India", "runs": 100}
    at.session_state["hl"] = (pa, pb)
    at.run()
    button(at, "Higher").click().run()  # 100 is not higher than 324 -> wrong
    assert not at.exception, at.exception

    feedback = [i.value for i in at.columns[0].children.values() if i.type in ("info", "alert")]
    assert len(feedback) == 1
    assert "Nathan Yardley 324 runs" in feedback[0] and "Previous Rival 100 runs" in feedback[0]
    assert "you said higher" in feedback[0] and "Not quite" in feedback[0]

    new_a, new_b = at.session_state["hl"]
    assert {new_a["full_name"], new_b["full_name"]}.isdisjoint({"Nathan Yardley", "Previous Rival"})
    shown = [k for k in at.columns[0].children.values() if k.type == "markdown"]
    assert any(new_b["full_name"] in k.value and k.value.startswith("vs ") for k in shown)


def test_higher_lower_feedback_is_replaced_every_round_and_xp_matches():
    at = open_page()
    at.session_state["hl"] = (
        {"full_name": "Low Runs", "country": "X", "runs": 100},
        {"full_name": "High Runs", "country": "Y", "runs": 324},
    )
    at.run()
    button(at, "Higher").click().run()  # correct
    first = at.session_state["hl_msg"]
    assert "Low Runs 100 runs vs High Runs 324 runs" in first and "Correct! +10 XP" in first
    assert at.session_state["xp"] == 10 and at.session_state["streak"] == 1

    pa, pb = at.session_state["hl"]  # round 2: answer whichever way is right
    right_guess = "Higher" if pb["runs"] >= pa["runs"] else "Lower"
    button(at, right_guess).click().run()
    second = at.session_state["hl_msg"]
    assert second != first and "Low Runs" not in second and "High Runs" not in second
    assert pa["full_name"] in second and pb["full_name"] in second
    assert [i.value for i in at.columns[0].children.values() if i.type in ("info", "alert")] == [
        second
    ]


# ------------------------------------------------------------------ Higher / Lower direction (screenshot case)
# 'Higher'/'Lower' is about the HIDDEN player compared with the SHOWN player.
CALLUM = {"full_name": "Callum Stanton", "country": "England", "runs": 8235}
RAVINDU = {"full_name": "Ravindu Madushanka", "country": "Sri Lanka", "runs": 10355}


@pytest.mark.parametrize(
    "shown,hidden,guess,right",
    [
        (8235, 10355, "higher", True),  # hidden player has more -> 'Higher' is right
        (8235, 10355, "lower", False),  # ... so 'Lower' is wrong (the reported round)
        (10355, 8235, "lower", True),  # hidden player has fewer -> 'Lower' is right
        (10355, 8235, "higher", False),
    ],
)
def test_direction_is_hidden_player_relative_to_shown_player(shown, hidden, guess, right):
    assert arcade.grade_higher_lower(shown, hidden, guess) is right


def test_feedback_explains_what_higher_and_lower_meant():
    wrong = arcade.higher_lower_feedback(CALLUM, RAVINDU, "lower", False, 0)
    assert (
        "you said lower, i.e. Ravindu Madushanka would have fewer career runs than Callum Stanton"
        in wrong
    )
    assert "Callum Stanton 8,235 runs vs Ravindu Madushanka 10,355 runs" in wrong
    assert wrong.endswith("Not quite.")
    right = arcade.higher_lower_feedback(CALLUM, RAVINDU, "higher", True, 10)
    assert "would have more career runs than Callum Stanton" in right and right.endswith(
        "Correct! +10 XP"
    )
    assert "Equal runs count as higher" in arcade.higher_lower_feedback(
        CALLUM, CALLUM, "higher", True, 10
    )


def play(guess_label: str, shown: dict, hidden: dict, streak: int = 0) -> AppTest:
    at = open_page()
    at.session_state["hl"] = (shown, hidden)
    at.session_state["streak"] = streak
    at.run()
    button(at, guess_label).click().run()
    assert not at.exception, at.exception
    return at


def test_page_lower_when_hidden_player_has_more_is_wrong_and_resets_streak():
    at = play("Lower", CALLUM, RAVINDU, streak=3)
    msg = at.session_state["hl_msg"]
    assert msg.endswith("Not quite.") and "fewer career runs than Callum Stanton" in msg
    assert at.session_state["streak"] == 0 and at.session_state["xp"] == 0


def test_page_higher_when_hidden_player_has_more_is_correct_and_scores():
    at = play("Higher", CALLUM, RAVINDU)
    assert at.session_state["hl_msg"].endswith("Correct! +10 XP")
    assert at.session_state["xp"] == 10 and at.session_state["streak"] == 1


def test_page_lower_when_hidden_player_has_fewer_is_correct():
    at = play("Lower", RAVINDU, CALLUM, streak=1)  # shown 10,355; hidden 8,235
    msg = at.session_state["hl_msg"]
    assert "Correct!" in msg and msg.endswith("+12 XP")
    # existing award(): streak 1 -> 2 gives multiplier 1 + (2 - 1) * 0.25 = 1.25; int(10 * 1.25) = 12
    assert at.session_state["streak"] == 2 and at.session_state["xp"] == 12


def test_page_higher_when_hidden_player_has_fewer_is_wrong():
    at = play("Higher", RAVINDU, CALLUM)
    assert at.session_state["hl_msg"].endswith("Not quite.") and at.session_state["xp"] == 0


def test_question_states_which_player_higher_or_lower_refers_to():
    at = open_page()
    at.session_state["hl"] = (CALLUM, RAVINDU)
    at.run()
    shown = [k.value for k in at.columns[0].children.values() if k.type == "markdown"]
    asked = next(v for v in shown if v.startswith("vs "))
    assert "Does Ravindu Madushanka have higher or lower career runs than Callum Stanton?" in asked