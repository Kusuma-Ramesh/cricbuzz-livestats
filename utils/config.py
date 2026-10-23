"""Central configuration.

Secrets are read (in order) from: Streamlit secrets -> environment / .env -> defaults.
Nothing sensitive is ever hard-coded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _secret(name: str, default: str = "") -> str:
    """Read a setting from st.secrets (if available) or the environment."""
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # secrets file missing or streamlit not running
        pass
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    app_name: str = "Cricbuzz LiveStats"
    rapidapi_key: str = ""
    rapidapi_host: str = "cricbuzz-cricket.p.rapidapi.com"
    database_url: str = f"sqlite:///{ROOT_DIR / 'data' / 'cricbuzz.db'}"
    api_cache_seconds: int = 30
    api_timeout: int = 10

    @property
    def has_api_key(self) -> bool:
        return bool(self.rapidapi_key) and self.rapidapi_key != "your_rapidapi_key_here"


def load_settings() -> Settings:
    url = _secret("DATABASE_URL", "")
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        # make relative SQLite paths relative to the project root
        url = f"sqlite:///{ROOT_DIR / url.replace('sqlite:///', '')}"
    return Settings(
        rapidapi_key=_secret("RAPIDAPI_KEY"),
        rapidapi_host=_secret("RAPIDAPI_HOST", "cricbuzz-cricket.p.rapidapi.com"),
        database_url=url or Settings.database_url,
        api_cache_seconds=int(_secret("API_CACHE_SECONDS", "30")),
        api_timeout=int(_secret("API_TIMEOUT_SECONDS", "10")),
    )


settings = load_settings()
