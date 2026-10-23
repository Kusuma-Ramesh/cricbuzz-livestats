"""Centralised database access layer (the only module that talks to the DB driver).

* Database-agnostic through SQLAlchemy (SQLite / MySQL / PostgreSQL).
* Parameterised queries only - user input is never string-formatted into SQL.
* A hardened read-only runner powers the custom SQL console.
"""

from __future__ import annotations

import logging
import math
import re
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator, Mapping

import pandas as pd
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from utils.config import settings

log = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised for any database failure, with a human-readable message."""


class UnsafeQueryError(DatabaseError):
    """Raised when a query submitted to the read-only console is not a plain SELECT."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create (once) and return the SQLAlchemy engine."""
    url = settings.database_url
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    try:
        engine = create_engine(url, **kwargs)
    except Exception as exc:  # bad URL / missing driver
        raise DatabaseError(f"Could not create database engine: {exc}") from exc

    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _sqlite_setup(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

            dbapi_conn.create_function(
                "SQRT",
                1,
                lambda x: None if x is None else math.sqrt(max(float(x), 0.0)),
            )
    return engine


# --------------------------------------------------------------------------- helpers
def _bind_names(sql: str) -> set[str]:
    return set(re.findall(r"(?<![:\w]):([A-Za-z_]\w*)", sql))


def _clean(exc: Exception) -> str:
    msg = str(getattr(exc, "orig", exc))
    return msg.splitlines()[0][:300] if msg else exc.__class__.__name__


# --------------------------------------------------------------------------- reads
def run_query(sql: str, params: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Run a parameterised SELECT and return a DataFrame."""
    wanted = _bind_names(sql)
    bound = {k: v for k, v in (params or {}).items() if k in wanted}
    try:
        with get_engine().connect() as conn:
            return pd.read_sql_query(text(sql), conn, params=bound)
    except SQLAlchemyError as exc:
        log.exception("Query failed")
        raise DatabaseError(_clean(exc)) from exc


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|"
    r"grant|revoke|vacuum|reindex|merge|call|exec|execute)\b",
    re.IGNORECASE,
)


def validate_readonly(sql: str) -> str:
    """Return a cleaned single SELECT/WITH statement or raise UnsafeQueryError."""
    cleaned = re.sub(r"--.*?$|/\*.*?\*/", " ", sql, flags=re.S | re.M).strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeQueryError("Write a SELECT query first.")
    if ";" in cleaned:
        raise UnsafeQueryError("Only one statement can be run at a time.")
    if not re.match(r"^(select|with)\b", cleaned, re.IGNORECASE):
        raise UnsafeQueryError("Only SELECT queries are allowed in the console.")
    hit = _FORBIDDEN.search(re.sub(r"'[^']*'", "''", cleaned))
    if hit:
        raise UnsafeQueryError(
            f"Keyword '{hit.group(0).upper()}' is not allowed in the read-only console."
        )
    return cleaned


def run_readonly(
    sql: str, params: Mapping[str, Any] | None = None, limit: int = 2000
) -> tuple[pd.DataFrame, float]:
    """Validated, read-only execution. Returns (DataFrame, elapsed_ms)."""
    cleaned = validate_readonly(sql)
    wanted = _bind_names(cleaned)
    bound = {k: v for k, v in (params or {}).items() if k in wanted}
    start = time.perf_counter()
    try:
        with get_engine().connect() as conn:
            if conn.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA query_only = ON")
            try:
                result = conn.execute(text(cleaned), bound)
                rows = result.fetchmany(limit)
                df = pd.DataFrame(rows, columns=list(result.keys()))
            finally:
                if conn.dialect.name == "sqlite":
                    conn.exec_driver_sql("PRAGMA query_only = OFF")
    except SQLAlchemyError as exc:
        raise DatabaseError(_clean(exc)) from exc
    return df, (time.perf_counter() - start) * 1000


def scalar(sql: str, params: Mapping[str, Any] | None = None, default: Any = None) -> Any:
    df = run_query(sql, params)
    if df.empty:
        return default
    value = df.iloc[0, 0]
    return default if pd.isna(value) else value


# --------------------------------------------------------------------------- writes
@contextmanager
def transaction() -> Iterator[Connection]:
    """Atomic unit of work: commits on success, rolls back on any exception."""
    try:
        with get_engine().begin() as conn:
            yield conn
    except SQLAlchemyError as exc:
        log.exception("Transaction rolled back")
        raise DatabaseError(_clean(exc)) from exc


def execute(sql: str, params: Mapping[str, Any] | None = None) -> int:
    """Run a single write statement in its own transaction. Returns affected rows."""
    with transaction() as conn:
        return conn.execute(text(sql), dict(params or {})).rowcount


# --------------------------------------------------------------------------- lifecycle
_READY = False


def ensure_database(force: bool = False) -> bool:
    """Create the schema and seed demo data on first run. Returns True if (re)seeded."""
    global _READY
    if _READY and not force:
        return False
    engine = get_engine()
    needs_seed = force
    if not needs_seed:
        try:
            insp = inspect(engine)
            needs_seed = (
                not insp.has_table("players")
                or scalar("SELECT COUNT(*) FROM players", default=0) == 0
            )
        except SQLAlchemyError as exc:
            raise DatabaseError(_clean(exc)) from exc
    if needs_seed:
        from database.seed import seed_database

        seed_database(engine)
    _READY = True
    return needs_seed


def db_health() -> dict[str, Any]:
    """Cheap status payload for the HUD."""
    try:
        engine = get_engine()
        n_players = int(scalar("SELECT COUNT(*) FROM players", default=0))
        n_matches = int(scalar("SELECT COUNT(*) FROM matches", default=0))
        return {
            "ok": True,
            "dialect": engine.dialect.name,
            "players": n_players,
            "matches": n_matches,
        }
    except Exception as exc:  # noqa: BLE001 - HUD must never crash the page
        return {"ok": False, "dialect": "n/a", "error": str(exc)[:120], "players": 0, "matches": 0}
