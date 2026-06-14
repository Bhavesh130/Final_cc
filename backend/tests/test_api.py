"""Integration tests for the HTTP API via the FastAPI TestClient.

These run the real app lifespan (GBM simulator + lazy DB init) against a temp
database, with the LLM mocked.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("LLM_MOCK", "true")
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)

    from app.db import reset_db_for_tests
    from app.main import create_app

    reset_db_for_tests()
    app = create_app()
    with TestClient(app) as c:
        yield c
    reset_db_for_tests()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_portfolio_default(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["cash_balance"] == 10000.0
    assert body["positions"] == []


def test_watchlist_default(client):
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    tickers = [w["ticker"] for w in r.json()["watchlist"]]
    assert "AAPL" in tickers
    assert len(tickers) == 10
    # Simulator seeds prices on start.
    aapl = next(w for w in r.json()["watchlist"] if w["ticker"] == "AAPL")
    assert aapl["price"] is not None


def test_trade_flow(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 2, "side": "buy"})
    assert r.status_code == 200
    body = r.json()
    assert body["trade"]["side"] == "buy"
    assert body["portfolio"]["cash_balance"] < 10000.0
    assert any(p["ticker"] == "AAPL" for p in body["portfolio"]["positions"])


def test_trade_validation_error(client):
    r = client.post(
        "/api/portfolio/trade", json={"ticker": "NVDA", "quantity": 100000, "side": "buy"}
    )
    assert r.status_code == 400


def test_watchlist_add_remove(client):
    r = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 200
    assert "PYPL" in [w["ticker"] for w in r.json()["watchlist"]]

    r = client.delete("/api/watchlist/PYPL")
    assert r.status_code == 200
    assert "PYPL" not in [w["ticker"] for w in r.json()["watchlist"]]


def test_watchlist_remove_missing(client):
    r = client.delete("/api/watchlist/ZZZZ")
    assert r.status_code == 404


def test_chat_mock_trade(client):
    r = client.post("/api/chat", json={"message": "buy 3 MSFT"})
    assert r.status_code == 200
    body = r.json()
    assert "[mock]" in body["message"]
    assert body["actions"]["trades"][0]["ticker"] == "MSFT"

    pf = client.get("/api/portfolio").json()
    assert any(p["ticker"] == "MSFT" for p in pf["positions"])


def test_history_endpoint(client):
    r = client.get("/api/portfolio/history")
    assert r.status_code == 200
    assert "snapshots" in r.json()
