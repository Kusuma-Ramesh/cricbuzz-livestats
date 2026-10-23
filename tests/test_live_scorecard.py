"""Live Matches: scorecard parsing, match-phase detection and the 'not started' message.

Fixtures below are REPRESENTATIVE (hand-written to the response shape api/parsers.py reads),
not captured from the live API.  Replace/extend them with sanitised real responses saved by
capture_samples.py when you have them.  No test touches the network.

Run:  python -m unittest tests.test_live_scorecard -v     (pytest also collects these)
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from api.parsers import (
    empty_scorecard_message,
    innings_totals,
    match_phase,
    parse_matches,
    parse_scorecard,
)

try:  # services.live_service imports streamlit
    import streamlit  # noqa: F401

    from api.cricbuzz_client import CricbuzzAPIError
    from services import live_service

    HAVE_STREAMLIT = True
except ImportError:  # pragma: no cover
    HAVE_STREAMLIT = False

START_MSG = "once the match starts"


# ----------------------------------------------------------------------------- fixtures
def _batters(n_out: int, total: int) -> dict:
    rows = {}
    for i in range(1, 12):
        rows[f"bat_{i}"] = {
            "batName": f"Batter {i}",
            "outDesc": f"c Fielder b Bowler {i}" if i <= n_out else "",
            "runs": total // 11,
            "balls": 30,
            "fours": 2,
            "sixes": 1,
            "strikeRate": 90.5,
        }
    return rows


def _innings(team: str, runs: int, wickets: int | None, n_out: int) -> dict:
    score = {"runs": runs, "overs": 49.2, "runRate": 5.4}
    if wickets is not None:
        score["wickets"] = wickets
    return {
        "inningsId": 1,
        "batTeamDetails": {"batTeamName": team, "batsmenData": _batters(n_out, runs)},
        "bowlTeamDetails": {
            "bowlTeamName": "Other",
            "bowlersData": {
                "bowl_1": {"bowlName": "Bowler 1", "overs": 10, "maidens": 1, "runs": 50, "wickets": 3, "economy": 5.0}
            },
        },
        "scoreDetails": score,
    }


def completed_scorecard() -> dict:
    return {
        "scoreCard": [
            _innings("South Africa", 301, 8, 8),
            _innings("Australia", 305, 5, 5),
        ],
        "isMatchComplete": True,
    }


def feed(state: str, status: str, with_scores: bool = True, **info_extra) -> dict:
    info = {
        "matchId": 101,
        "seriesName": "RSA v AUS ODI Series",
        "matchDesc": "1st ODI",
        "matchFormat": "ODI",
        "state": state,
        "status": status,
        "team1": {"teamName": "South Africa", "teamSName": "RSA"},
        "team2": {"teamName": "Australia", "teamSName": "AUS"},
        "venueInfo": {"ground": "Newlands", "city": "Cape Town"},
    }
    info.update(info_extra)
    match = {"matchInfo": info}
    if with_scores:
        match["matchScore"] = {
            "team1Score": {"inngs1": {"runs": 301, "wickets": 8, "overs": 50.0}},
            "team2Score": {"inngs1": {"runs": 305, "wickets": 5, "overs": 47.1}},
        }
    return {"typeMatches": [{"seriesMatches": [{"seriesAdWrapper": {"seriesName": "x", "matches": [match]}}]}]}


def first_match(payload: dict) -> dict:
    return parse_matches(payload)[0]


# ----------------------------------------------------------------------------- parse_scorecard
class ParseScorecardTests(unittest.TestCase):
    def test_completed_match_scorecard(self):
        inns = parse_scorecard(completed_scorecard())
        self.assertEqual([i["team"] for i in inns], ["South Africa", "Australia"])
        self.assertEqual((inns[0]["runs"], inns[0]["wkts"]), (301, 8))
        self.assertEqual(len(inns[0]["batting"]), 11)
        self.assertEqual(list(inns[0]["bowling"].columns), ["Bowler", "O", "M", "R", "W", "Econ"])
        self.assertEqual(inns[0]["batting"]["Dismissal"].iloc[-1], "not out")

    def test_all_out_innings_without_wickets_field_counts_dismissals(self):
        inns = parse_scorecard({"scoreCard": [_innings("Australia", 264, None, 10)]})
        self.assertEqual(inns[0]["wkts"], 10)

    def test_missing_optional_blocks_still_returns_innings(self):
        payload = {"scoreCard": [{"scoreDetails": {"runs": 120, "wickets": 4, "overs": 20}}]}
        inns = parse_scorecard(payload)
        self.assertEqual(len(inns), 1)
        self.assertTrue(inns[0]["batting"].empty and inns[0]["bowling"].empty)
        self.assertEqual(inns[0]["runs"], 120)

    def test_list_shaped_batsmen_data_is_accepted(self):
        inn = _innings("India", 200, 3, 3)
        inn["batTeamDetails"]["batsmenData"] = list(inn["batTeamDetails"]["batsmenData"].values())
        self.assertEqual(len(parse_scorecard({"scoreCard": [inn]})[0]["batting"]), 11)

    def test_unexpected_shapes_never_raise(self):
        for payload in (
            None, [], "oops", 42, {}, {"scoreCard": None}, {"scoreCard": "x"}, {"scoreCard": []},
            {"scoreCard": [None, 5, "x", {}]}, {"scoreCard": [{"batTeamDetails": "bad"}]},
            {"message": "no scorecard for this match"},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(parse_scorecard(payload), [])


# ----------------------------------------------------------------------------- parse_matches
class ParseMatchesTests(unittest.TestCase):
    def test_completed_match_fields(self):
        m = first_match(feed("Complete", "South Africa won by 3 runs"))
        self.assertFalse(m["is_live"])
        self.assertEqual(m["score1"]["runs"], 301)
        self.assertEqual(m["score2"]["wkts"], 5)

    def test_all_out_side_without_wickets_in_feed_defaults_to_ten(self):
        payload = feed("Complete", "Australia won by 5 wkts")
        score = payload["typeMatches"][0]["seriesMatches"][0]["seriesAdWrapper"]["matches"][0]["matchScore"]
        del score["team1Score"]["inngs1"]["wickets"]
        self.assertEqual(first_match(payload)["score1"]["wkts"], 10)

    def test_unexpected_shapes_never_raise(self):
        for payload in (None, [], "x", {}, {"typeMatches": None}, {"typeMatches": ["x", 3]},
                        {"typeMatches": [{"seriesMatches": [{"seriesAdWrapper": "bad"}]}]},
                        {"typeMatches": [{"seriesMatches": [{"seriesAdWrapper": {"matches": [{"matchInfo": None}]}}]}]}):
            with self.subTest(payload=payload):
                self.assertIsInstance(parse_matches(payload), list)


# ----------------------------------------------------------------------------- phase + message
class MatchPhaseTests(unittest.TestCase):
    def test_completed_by_state(self):
        self.assertEqual(match_phase(first_match(feed("Complete", "South Africa won by 3 runs"))), "completed")

    def test_completed_when_state_missing_uses_result_text(self):
        m = first_match(feed("", "Australia won by 5 wkts"))
        self.assertEqual(match_phase(m), "completed")

    def test_completed_with_scores_missing_is_still_completed(self):
        m = first_match(feed("Complete", "Match drawn", with_scores=False))
        self.assertEqual(match_phase(m), "completed")

    def test_live(self):
        self.assertEqual(match_phase(first_match(feed("In Progress", "RSA need 40 runs"))), "live")
        self.assertEqual(match_phase(first_match(feed("Stumps", "Day 2: Stumps"))), "live")

    def test_unknown_state_but_runs_on_board_is_not_upcoming(self):
        self.assertEqual(match_phase(first_match(feed("", "", with_scores=True))), "live")

    def test_upcoming(self):
        for state, status in (("Upcoming", "Match starts at 14:00"), ("Preview", ""), ("Toss", "Toss delayed")):
            with self.subTest(state=state):
                self.assertEqual(match_phase(first_match(feed(state, status, with_scores=False))), "upcoming")

    def test_future_start_date_is_upcoming(self):
        future_ms = int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp() * 1000)
        m = first_match(feed("", "", with_scores=False, startDate=str(future_ms)))
        self.assertEqual(match_phase(m), "upcoming")

    def test_unknown_and_garbage_input(self):
        self.assertEqual(match_phase(first_match(feed("", "", with_scores=False))), "unknown")
        for bad in (None, {}, "x", {"state": None, "status": None, "score1": None}):
            with self.subTest(bad=bad):
                self.assertIn(match_phase(bad), {"unknown"})


class EmptyScorecardMessageTests(unittest.TestCase):
    def test_completed_match_never_says_it_will_start(self):
        """Regression: a finished match with an empty scorecard used to show 'once the match starts'."""
        m = first_match(feed("Complete", "South Africa won by 3 runs"))
        level, text = empty_scorecard_message(m)
        self.assertEqual(level, "warning")
        self.assertNotIn(START_MSG, text)
        self.assertIn("complete", text.lower())
        self.assertIn("totals", text.lower())  # feed totals are offered

    def test_completed_without_scores_or_state_still_not_start_message(self):
        m = first_match(feed("", "Match tied", with_scores=False))
        self.assertNotIn(START_MSG, empty_scorecard_message(m)[1])

    def test_upcoming_keeps_start_message(self):
        m = first_match(feed("Upcoming", "Starts Sat", with_scores=False))
        self.assertEqual(empty_scorecard_message(m), ("info", "Scorecard will appear once the match starts."))

    def test_live_and_unknown_wording(self):
        live = empty_scorecard_message(first_match(feed("In Progress", "")))[1]
        unknown = empty_scorecard_message(first_match(feed("", "", with_scores=False)))[1]
        self.assertNotIn(START_MSG, live)
        self.assertNotIn(START_MSG, unknown)

    def test_innings_totals_come_from_feed_data(self):
        rows = innings_totals(first_match(feed("Complete", "South Africa won by 3 runs")))
        self.assertEqual([r["Score"] for r in rows], ["301/8", "305/5"])
        self.assertEqual(innings_totals({}), [])


# ----------------------------------------------------------------------------- service layer
@unittest.skipUnless(HAVE_STREAMLIT, "streamlit not installed")
class GetScorecardTests(unittest.TestCase):
    def setUp(self):
        self.match = first_match(feed("Complete", "South Africa won by 3 runs"))
        self.sentinel = [{"team": "SIMULATED"}]

    def test_api_returns_nothing_parseable_gives_empty_not_simulated(self):
        with mock.patch.object(live_service, "_fetch_scorecard", return_value=[]), mock.patch.object(
            live_service, "demo_scorecard", side_effect=AssertionError("demo data must not be used")
        ):
            self.assertEqual(live_service.get_scorecard(self.match, "api"), ([], ""))

    def test_api_data_is_returned_untouched(self):
        real = parse_scorecard(completed_scorecard())
        with mock.patch.object(live_service, "_fetch_scorecard", return_value=real):
            innings, note = live_service.get_scorecard(self.match, "api")
        self.assertIs(innings, real)
        self.assertEqual(note, "")

    def test_missing_match_id_does_not_crash_or_simulate(self):
        for bad in ({**self.match, "match_id": None}, {k: v for k, v in self.match.items() if k != "match_id"}):
            with self.subTest(bad=bad.get("match_id")), mock.patch.object(
                live_service, "demo_scorecard", side_effect=AssertionError("demo data must not be used")
            ):
                innings, note = live_service.get_scorecard(bad, "api")
                self.assertEqual(innings, [])
                self.assertIn("match id", note)

    def test_api_error_keeps_existing_labelled_fallback(self):
        with mock.patch.object(live_service, "_fetch_scorecard", side_effect=CricbuzzAPIError("boom", 500)), mock.patch.object(
            live_service, "demo_scorecard", return_value=self.sentinel
        ):
            innings, note = live_service.get_scorecard(self.match, "api")
        self.assertEqual(innings, self.sentinel)
        self.assertIn("simulated", note)

    def test_force_demo_still_uses_demo_scorecard(self):
        with mock.patch.object(live_service, "demo_scorecard", return_value=self.sentinel):
            self.assertEqual(live_service.get_scorecard(self.match, "demo"), (self.sentinel, ""))


if __name__ == "__main__":
    unittest.main()