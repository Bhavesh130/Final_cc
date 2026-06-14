"""Pytest configuration and fixtures."""

import asyncio

import pytest


@pytest.fixture
def event_loop_policy():
    """Use the default event loop policy for all async tests."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point the app at a fresh temp SQLite DB, seeded on init."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(db_file))

    from app.db import init_db, reset_db_for_tests

    reset_db_for_tests()
    init_db()
    yield db_file
    reset_db_for_tests()


@pytest.fixture
def price_cache():
    """A PriceCache pre-populated with seed prices for the default tickers."""
    from app.market import PriceCache
    from app.market.seed_prices import SEED_PRICES

    cache = PriceCache()
    for ticker, price in SEED_PRICES.items():
        cache.update(ticker, price)
    return cache


class FakeSource:
    """Minimal MarketDataSource stand-in for tests."""

    def __init__(self, cache):
        self.cache = cache
        self.added = []
        self.removed = []

    async def start(self, tickers):
        for t in tickers:
            self.cache.update(t, 100.0)

    async def stop(self):
        pass

    async def add_ticker(self, ticker):
        self.added.append(ticker)
        self.cache.update(ticker, 100.0)

    async def remove_ticker(self, ticker):
        self.removed.append(ticker)
        self.cache.remove(ticker)

    def get_tickers(self):
        return list(self.cache.get_all().keys())


@pytest.fixture
def fake_source(price_cache):
    return FakeSource(price_cache)
