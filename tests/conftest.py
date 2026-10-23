"""Test fixtures: an isolated, freshly seeded SQLite database (the real app DB is never touched)."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp(prefix="cricbuzz_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["RAPIDAPI_KEY"] = ""

import pytest  # noqa: E402

from utils.db_connection import ensure_database  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    ensure_database(force=True)
    yield
