"""Thin, defensive client for the Cricbuzz Cricket API on RapidAPI.

Features: timeouts, retry with exponential back-off on 429/5xx/network errors,
rate-limit awareness, and human-readable CricbuzzAPIError messages.
Endpoint paths follow the RapidAPI playground for `cricbuzz-cricket`; confirm any
path/parameter in your own playground if the provider changes it.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from utils.config import settings

log = logging.getLogger(__name__)


class CricbuzzAPIError(RuntimeError):
    """Any failure talking to the API (auth, quota, network, bad JSON)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class CricbuzzClient:
    def __init__(
        self,
        key: str | None = None,
        host: str | None = None,
        timeout: int | None = None,
        retries: int = 3,
    ):
        self.key = key or settings.rapidapi_key
        self.host = host or settings.rapidapi_host
        self.timeout = timeout or settings.api_timeout
        self.retries = retries
        self.remaining: str | None = None
        self.session = requests.Session()

    # ------------------------------------------------------------------ core
    @property
    def configured(self) -> bool:
        return bool(self.key) and self.key != "your_rapidapi_key_here"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.configured:
            raise CricbuzzAPIError(
                "No RAPIDAPI_KEY configured - add it to .env or Streamlit secrets.", 401
            )
        url = f"https://{self.host}{path}"
        headers = {"x-rapidapi-key": self.key, "x-rapidapi-host": self.host}
        last: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
                self.remaining = resp.headers.get("x-ratelimit-requests-remaining", self.remaining)
                if resp.status_code in (401, 403):
                    raise CricbuzzAPIError(
                        "API key rejected or not subscribed to this API (HTTP %s)."
                        % resp.status_code,
                        resp.status_code,
                    )
                if resp.status_code == 404:
                    raise CricbuzzAPIError(f"Endpoint not found: {path}", 404)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise CricbuzzAPIError(
                        f"Temporary API problem (HTTP {resp.status_code}).", resp.status_code
                    )
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError as exc:
                    raise CricbuzzAPIError("API returned invalid JSON.") from exc
            except CricbuzzAPIError as exc:
                last = exc
                if exc.status not in (429, 500, 502, 503, 504):  # not worth retrying
                    raise
            except (requests.Timeout, requests.ConnectionError) as exc:
                last = CricbuzzAPIError(f"Network problem: {exc.__class__.__name__}")
            except requests.RequestException as exc:
                raise CricbuzzAPIError(f"Request failed: {exc}") from exc
            if attempt < self.retries:
                time.sleep(0.6 * 2 ** (attempt - 1))
        raise last or CricbuzzAPIError("Unknown API failure.")

    # ------------------------------------------------------------- endpoints
    def live_matches(self):
        return self._get("/matches/v1/live")

    def recent_matches(self):
        return self._get("/matches/v1/recent")

    def upcoming_matches(self):
        return self._get("/matches/v1/upcoming")

    def match_info(self, match_id: int):
        return self._get(f"/mcenter/v1/{match_id}")

    def scorecard(self, match_id: int):
        return self._get(f"/mcenter/v1/{match_id}/scard")

    def commentary(self, match_id: int):
        return self._get(f"/mcenter/v1/{match_id}/comm")

    def series_list(self, year: int):
        return self._get("/series/v1/archives/international", {"year": year})

    def teams(self):
        return self._get("/teams/v1/international")

    def team_players(self, team_id: int):
        return self._get(f"/teams/v1/{team_id}/players")

    def venue(self, venue_id: int):
        return self._get(f"/venues/v1/{venue_id}")

    def player_search(self, name: str):
        return self._get("/stats/v1/player/search", {"plrN": name})

    def player_info(self, pid: int):
        return self._get(f"/stats/v1/player/{pid}")

    def player_batting(self, pid: int):
        return self._get(f"/stats/v1/player/{pid}/batting")

    def player_bowling(self, pid: int):
        return self._get(f"/stats/v1/player/{pid}/bowling")

    def rankings(self, category: str = "batsmen", fmt: str = "odi"):
        return self._get(f"/stats/v1/rankings/{category}", {"formatType": fmt})

    def top_stats(
        self, stats_type: str = "mostRuns", match_type: int | None = None, year: int | None = None
    ):
        """stats_type e.g. mostRuns, highestScore, highestAvg, highestSr, mostHundreds, mostSixes,
        mostWickets, lowestAvg, lowestEcon, mostFiveWickets."""
        params: dict[str, Any] = {"statsType": stats_type}
        if match_type:
            params["matchType"] = match_type  # 1 = Test, 2 = ODI, 3 = T20I
        if year:
            params["year"] = year
        return self._get("/stats/v1/topstats/0", params)
