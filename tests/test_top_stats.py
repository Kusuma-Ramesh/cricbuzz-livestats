"""Top Player Stats from the API: header alignment and leaderboard column choice.

FIXTURE_ROWS are the first rows of a real `mostRuns` response, as captured from the live API
(public player statistics, no credentials).  The API sends one header fewer than values per row:
the first value is the player id.  No test touches the network.

Run:  python -m unittest tests.test_top_stats -v
"""

from __future__ import annotations

import unittest

import pandas as pd

from api.parsers import build_api_board, parse_table

HEADERS = ["Batter", "M", "I", "R", "SR"]  # five labels...
FIXTURE_ROWS = [  # ...for six values: id, name, matches, innings, runs, strike rate
    ["8359", "Babar Azam", "144", "136", "4596", "128.02"],
    ["2258", "Jos Buttler", "163", "150", "4384", "150.14"],
    ["576", "Rohit Sharma", "159", "151", "4231", "140.89"],
    ["1413", "Virat Kohli", "125", "117", "4188", "137.04"],
    ["1114", "Paul Stirling", "163", "160", "3895", "134.36"],
]


def payload(rows=FIXTURE_ROWS, headers=HEADERS):
    return {"headers": headers, "values": [{"values": r} for r in rows]}


class ParseTableTests(unittest.TestCase):
    def test_leading_id_aligns_headers_with_data(self):
        df = parse_table(payload(), leading_id="player_id")
        self.assertEqual(list(df.columns), ["player_id", "Batter", "M", "I", "R", "SR"])
        self.assertEqual(df.loc[0, "Batter"], "Babar Azam")
        self.assertEqual(int(df.loc[0, "R"]), 4596)
        self.assertAlmostEqual(float(df.loc[0, "SR"]), 128.02)

    def test_default_behaviour_is_unchanged_for_other_endpoints(self):
        df = parse_table(payload())
        self.assertEqual(list(df.columns), ["Batter", "M", "I", "R", "SR", "col_5"])

    def test_no_shift_when_headers_already_complete(self):
        rows = [r[1:] for r in FIXTURE_ROWS]  # five values for five headers
        df = parse_table(payload(rows), leading_id="player_id")
        self.assertEqual(list(df.columns), HEADERS)

    def test_unexpected_shapes_never_raise(self):
        for bad in (None, [], "x", 3, {}, {"headers": None, "values": None}, {"values": "x"},
                    {"headers": ["a"], "values": [None, 5, "x", {"values": None}]}):
            with self.subTest(bad=bad):
                self.assertTrue(parse_table(bad, leading_id="player_id").empty)


class BuildApiBoardTests(unittest.TestCase):
    def setUp(self):
        self.df = parse_table(payload(), leading_id="player_id")

    def test_most_runs_uses_runs_not_the_last_column(self):
        """Regression: the page used to show the strike rate (128, 150, 141) as 'most runs'."""
        board = build_api_board(self.df)
        self.assertEqual(board["value"].tolist(), [4596, 4384, 4231, 4188, 3895])
        self.assertEqual(board["name"].iloc[0], "Babar Azam")
        self.assertEqual(board["sub"].iloc[0], "144 matches")

    def test_works_with_object_and_pandas_string_text_columns(self):
        as_object = self.df.copy()
        as_object["Batter"] = as_object["Batter"].astype(object)
        as_str = self.df.copy()
        as_str["Batter"] = as_str["Batter"].astype("string")
        for frame in (as_object, as_str):
            with self.subTest(dtype=str(frame["Batter"].dtype)):
                self.assertEqual(build_api_board(frame)["value"].iloc[0], 4596)

    def test_ascending_stat_picks_the_ascending_column(self):
        df = pd.DataFrame(
            {"player_id": [1, 2, 3], "Bowler": ["A", "B", "C"], "M": [50, 40, 60], "Econ": [4.1, 4.5, 4.9]}
        )
        self.assertEqual(build_api_board(df, ascending=True)["value"].tolist(), [4.1, 4.5, 4.9])

    def test_falls_back_to_last_numeric_column_when_nothing_is_ordered(self):
        df = pd.DataFrame({"Name": ["A", "B", "C"], "x": [3, 1, 2], "y": [5, 9, 7]})
        self.assertEqual(build_api_board(df)["value"].tolist(), [5, 9, 7])

    def test_unusable_tables_give_an_empty_board(self):
        for bad in (None, [], pd.DataFrame(), pd.DataFrame({"a": [1, 2], "b": [3, 4]}),
                    pd.DataFrame({"a": ["x", "y"], "b": ["p", "q"]})):
            with self.subTest(bad=type(bad).__name__):
                self.assertTrue(build_api_board(bad).empty)


if __name__ == "__main__":
    unittest.main()