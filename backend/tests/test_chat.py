"""Tests for the chat service in mock mode."""

import pytest


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")


async def test_mock_analysis_response(temp_db, price_cache, fake_source):
    from app.services import chat as svc

    res = await svc.handle_chat("how is my portfolio?", price_cache, fake_source)
    assert "[mock]" in res["message"]
    assert res["actions"]["trades"] == []


async def test_mock_executes_buy(temp_db, price_cache, fake_source):
    from app.services import chat as svc

    res = await svc.handle_chat("buy 5 AAPL", price_cache, fake_source)
    trades = res["actions"]["trades"]
    assert len(trades) == 1
    assert trades[0]["status"] == "executed"
    assert trades[0]["ticker"] == "AAPL"
    assert trades[0]["quantity"] == 5

    from app.services import portfolio as pf_svc

    pf = pf_svc.get_portfolio(price_cache)
    assert any(p["ticker"] == "AAPL" for p in pf["positions"])


async def test_mock_rejects_overspend(temp_db, price_cache, fake_source):
    from app.services import chat as svc

    res = await svc.handle_chat("buy 1000 NVDA", price_cache, fake_source)
    trades = res["actions"]["trades"]
    assert trades[0]["status"] == "rejected"
    assert "Insufficient" in trades[0]["error"]


async def test_mock_watchlist_add(temp_db, price_cache, fake_source):
    from app.services import chat as svc

    res = await svc.handle_chat("add PYPL to my watchlist", price_cache, fake_source)
    changes = res["actions"]["watchlist_changes"]
    assert any(c["ticker"] == "PYPL" and c["status"] == "applied" for c in changes)


async def test_history_persisted(temp_db, price_cache, fake_source):
    from app.services import chat as svc

    await svc.handle_chat("hello", price_cache, fake_source)
    history = svc.get_chat_history()
    assert len(history) == 2  # user + assistant
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"


async def test_empty_message_raises(temp_db, price_cache, fake_source):
    from app.services import chat as svc

    with pytest.raises(ValueError):
        await svc.handle_chat("   ", price_cache, fake_source)
