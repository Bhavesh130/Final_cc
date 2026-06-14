"""Tests for the watchlist service."""

import pytest

from app.config import DEFAULT_TICKERS
from app.services import watchlist as svc


def test_seed_watchlist(temp_db):
    assert svc.get_tickers() == DEFAULT_TICKERS


def test_list_includes_prices(temp_db, price_cache):
    items = svc.list_watchlist(price_cache)
    aapl = next(i for i in items if i["ticker"] == "AAPL")
    assert aapl["price"] == 190.0


async def test_add_ticker(temp_db, fake_source):
    ticker = await svc.add_ticker("pypl", fake_source)
    assert ticker == "PYPL"
    assert "PYPL" in svc.get_tickers()
    assert "PYPL" in fake_source.added


async def test_add_duplicate_raises(temp_db, fake_source):
    with pytest.raises(svc.WatchlistError):
        await svc.add_ticker("AAPL", fake_source)


async def test_add_invalid_raises(temp_db, fake_source):
    with pytest.raises(svc.WatchlistError):
        await svc.add_ticker("123!", fake_source)


async def test_remove_ticker(temp_db, fake_source):
    await svc.remove_ticker("AAPL", fake_source)
    assert "AAPL" not in svc.get_tickers()
    assert "AAPL" in fake_source.removed


async def test_remove_missing_raises(temp_db, fake_source):
    with pytest.raises(svc.WatchlistError):
        await svc.remove_ticker("ZZZZ", fake_source)


async def test_remove_held_ticker_keeps_streaming(temp_db, fake_source, price_cache):
    from app.services import portfolio as pf_svc

    pf_svc.execute_trade("AAPL", 1, "buy", price_cache)
    await svc.remove_ticker("AAPL", fake_source)
    assert "AAPL" not in svc.get_tickers()
    # Still held → source not told to stop streaming it.
    assert "AAPL" not in fake_source.removed
