"""SQLite connection management and lazy initialization.

A single SQLite file backs the whole app. We open a short-lived connection per
operation (SQLite is happy with this, especially in WAL mode) and guard the
one-time schema creation + seeding with a process-wide lock.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.config import DEFAULT_TICKERS, DEFAULT_USER_ID, STARTING_CASH, get_db_path

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_init_lock = Lock()
_initialized = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection, committing on success and rolling back on error.

    Ensures the database is initialized (schema + seed) before first use.
    """
    init_db()
    conn = _connect(get_db_path())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the schema and seed default data if not already done.

    Idempotent and safe to call on every request — the actual work happens at
    most once per process (and the seed only inserts when tables are empty).
    """
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        conn = _connect(get_db_path())
        try:
            conn.executescript(_SCHEMA_PATH.read_text())
            _seed(conn)
            conn.commit()
        finally:
            conn.close()
        _initialized = True


def _seed(conn: sqlite3.Connection) -> None:
    """Insert the default user and watchlist if the database is fresh."""
    row = conn.execute(
        "SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            (DEFAULT_USER_ID, STARTING_CASH, _now()),
        )

    count = conn.execute(
        "SELECT COUNT(*) AS n FROM watchlist WHERE user_id = ?", (DEFAULT_USER_ID,)
    ).fetchone()["n"]
    if count == 0:
        now = _now()
        conn.executemany(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            [(str(uuid.uuid4()), DEFAULT_USER_ID, t, now) for t in DEFAULT_TICKERS],
        )


def reset_db_for_tests() -> None:
    """Force re-initialization on next access (test helper)."""
    global _initialized
    with _init_lock:
        _initialized = False
