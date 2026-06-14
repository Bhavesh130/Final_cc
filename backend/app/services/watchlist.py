"""Watchlist service: CRUD synced with the live market data source."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.config import DEFAULT_USER_ID
from app.db import get_connection
from app.market import MarketDataSource, PriceCache

_TICKER_RE = re.compile(r"^[A-Z][A-Z.\-]{0,9}$")


class WatchlistError(ValueError):
    """Raised on invalid watchlist operations."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(ticker: str) -> str:
    ticker = (ticker or "").strip().upper()
    if not _TICKER_RE.match(ticker):
        raise WatchlistError(f"Invalid ticker symbol: '{ticker}'.")
    return ticker


def get_tickers() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
            (DEFAULT_USER_ID,),
        ).fetchall()
    return [r["ticker"] for r in rows]


def list_watchlist(price_cache: PriceCache) -> list[dict]:
    """Return watchlist tickers enriched with the latest cached price."""
    items = []
    for ticker in get_tickers():
        update = price_cache.get(ticker)
        if update is not None:
            items.append({"ticker": ticker, **_price_fields(update)})
        else:
            items.append(
                {
                    "ticker": ticker,
                    "price": None,
                    "previous_price": None,
                    "change": 0.0,
                    "change_percent": 0.0,
                    "direction": "flat",
                }
            )
    return items


def _price_fields(update) -> dict:
    d = update.to_dict()
    return {
        "price": d["price"],
        "previous_price": d["previous_price"],
        "change": d["change"],
        "change_percent": d["change_percent"],
        "direction": d["direction"],
    }


async def add_ticker(ticker: str, source: MarketDataSource) -> str:
    """Add a ticker to the watchlist and start streaming it. Returns the ticker."""
    ticker = _normalize(ticker)
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?",
            (DEFAULT_USER_ID, ticker),
        ).fetchone()
        if exists:
            raise WatchlistError(f"{ticker} is already in the watchlist.")
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, _now()),
        )
    await source.add_ticker(ticker)
    return ticker


async def remove_ticker(ticker: str, source: MarketDataSource) -> str:
    """Remove a ticker from the watchlist. Stops streaming if not held.

    A ticker that backs an open position keeps streaming so the position can
    still be valued; only its watchlist row is removed.
    """
    ticker = _normalize(ticker)
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (DEFAULT_USER_ID, ticker),
        )
        if cur.rowcount == 0:
            raise WatchlistError(f"{ticker} is not in the watchlist.")
        held = conn.execute(
            "SELECT 1 FROM positions WHERE user_id = ? AND ticker = ?",
            (DEFAULT_USER_ID, ticker),
        ).fetchone()

    if not held:
        await source.remove_ticker(ticker)
    return ticker
