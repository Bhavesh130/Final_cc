"""Database subsystem: lazy-initialized SQLite store."""

from .database import get_connection, init_db, reset_db_for_tests

__all__ = ["get_connection", "init_db", "reset_db_for_tests"]
