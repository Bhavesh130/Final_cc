"""Tests for the portfolio service."""

import pytest

from app.services import portfolio as svc


def test_seed_starts_with_10k(temp_db, price_cache):
    pf = svc.get_portfolio(price_cache)
    assert pf["cash_balance"] == 10000.0
    assert pf["positions"] == []
    assert pf["total_value"] == 10000.0


def test_buy_reduces_cash_and_creates_position(temp_db, price_cache):
    res = svc.execute_trade("AAPL", 10, "buy", price_cache)
    assert res["side"] == "buy"
    assert res["price"] == 190.0
    assert res["trade_value"] == 1900.0

    pf = svc.get_portfolio(price_cache)
    assert pf["cash_balance"] == 8100.0
    assert len(pf["positions"]) == 1
    pos = pf["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 190.0


def test_weighted_average_cost(temp_db, price_cache):
    svc.execute_trade("AAPL", 10, "buy", price_cache)  # @190
    price_cache.update("AAPL", 210.0)
    svc.execute_trade("AAPL", 10, "buy", price_cache)  # @210
    pf = svc.get_portfolio(price_cache)
    pos = pf["positions"][0]
    assert pos["quantity"] == 20
    assert pos["avg_cost"] == 200.0  # (1900 + 2100) / 20


def test_sell_increases_cash_and_reduces_position(temp_db, price_cache):
    svc.execute_trade("AAPL", 10, "buy", price_cache)
    svc.execute_trade("AAPL", 4, "sell", price_cache)
    pf = svc.get_portfolio(price_cache)
    pos = pf["positions"][0]
    assert pos["quantity"] == 6
    # 10000 - 1900 + 760
    assert pf["cash_balance"] == 8860.0


def test_sell_all_removes_position(temp_db, price_cache):
    svc.execute_trade("AAPL", 10, "buy", price_cache)
    svc.execute_trade("AAPL", 10, "sell", price_cache)
    pf = svc.get_portfolio(price_cache)
    assert pf["positions"] == []
    assert pf["cash_balance"] == 10000.0


def test_unrealized_pnl(temp_db, price_cache):
    svc.execute_trade("AAPL", 10, "buy", price_cache)  # cost 1900
    price_cache.update("AAPL", 200.0)
    pf = svc.get_portfolio(price_cache)
    pos = pf["positions"][0]
    assert pos["unrealized_pnl"] == 100.0
    assert pos["unrealized_pnl_percent"] == pytest.approx(5.26, abs=0.01)


def test_insufficient_cash_raises(temp_db, price_cache):
    with pytest.raises(svc.TradeError):
        svc.execute_trade("NVDA", 1000, "buy", price_cache)  # 800k > 10k


def test_insufficient_shares_raises(temp_db, price_cache):
    svc.execute_trade("AAPL", 5, "buy", price_cache)
    with pytest.raises(svc.TradeError):
        svc.execute_trade("AAPL", 10, "sell", price_cache)


def test_unknown_price_raises(temp_db, price_cache):
    with pytest.raises(svc.TradeError):
        svc.execute_trade("ZZZZ", 1, "buy", price_cache)


def test_invalid_inputs(temp_db, price_cache):
    with pytest.raises(svc.TradeError):
        svc.execute_trade("AAPL", -1, "buy", price_cache)
    with pytest.raises(svc.TradeError):
        svc.execute_trade("AAPL", 1, "hold", price_cache)


def test_history_records_snapshots(temp_db, price_cache):
    svc.record_snapshot(price_cache)
    svc.execute_trade("AAPL", 1, "buy", price_cache)  # snapshots after trade
    history = svc.get_history()
    assert len(history) >= 2
    assert all("total_value" in h and "recorded_at" in h for h in history)
