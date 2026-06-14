"""Application configuration loaded from environment variables.

The project root `.env` is loaded once on import. We tolerate two spellings of
the OpenRouter key (`OPENROUTER_API_KEY` and `OPEN_ROUTER_API_KEY`) because the
provisioned `.env` uses the underscored variant while the plan/docs use the
canonical one.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/app/config.py -> parents[2] == project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Load the project-root .env if present (no-op in Docker where env is injected).
load_dotenv(PROJECT_ROOT / ".env")


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_openrouter_api_key() -> str:
    """Return the OpenRouter API key, tolerating both env-var spellings."""
    return (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPEN_ROUTER_API_KEY")
        or ""
    ).strip()


def llm_mock_enabled() -> bool:
    """Whether to short-circuit the LLM with deterministic mock responses."""
    return _truthy(os.environ.get("LLM_MOCK"))


def get_db_path() -> Path:
    """Absolute path to the SQLite database file.

    Defaults to `<project_root>/db/finally.db`. In Docker the container sets
    `FINALLY_DB_PATH=/app/db/finally.db` (a mounted volume).
    """
    env_path = os.environ.get("FINALLY_DB_PATH")
    if env_path:
        return Path(env_path)
    return PROJECT_ROOT / "db" / "finally.db"


def get_static_dir() -> Path:
    """Directory containing the built frontend (Next.js static export).

    In Docker the frontend export is copied to `/app/static`. In dev we fall
    back to `frontend/out` if it exists.
    """
    env_dir = os.environ.get("FINALLY_STATIC_DIR")
    if env_dir:
        return Path(env_dir)
    docker_static = Path("/app/static")
    if docker_static.exists():
        return docker_static
    return PROJECT_ROOT / "frontend" / "out"


# Default watchlist seeded on first launch (PLAN §7).
DEFAULT_TICKERS: list[str] = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

DEFAULT_USER_ID = "default"
STARTING_CASH = 10_000.0
