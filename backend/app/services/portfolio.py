"""Portfolio service: valuation, trade execution, and history.

Market orders only, instant fill at the latest cached price, no fees. The
price cache is the single source of truth for current prices.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.config import DEFAULT_USER_ID
from app.db import get_connection
from app.market import PriceCache

# Treat sub-cent / sub-micro-share residuals as zero to avoid float dust.
_EPSILON = 1e-9


class TradeError(ValueError):
    """Raised when a trade fails validation (insufficient cash/shares, etc.)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_cash_balance() -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
        ).fetchone()
        return float(row["cash_balance"]) if row else 0.0


def get_portfolio(price_cache: PriceCache) -> dict:
    """Return full portfolio state: cash, positions with P&L, totals."""
    with get_connection() as conn:
        cash = float(
            conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?",
                (DEFAULT_USER_ID,),
            ).fetchone()["cash_balance"]
        )
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions "
            "WHERE user_id = ? ORDER BY ticker",
            (DEFAULT_USER_ID,),
        ).fetchall()

    positions = []
    positions_value = 0.0
    total_unrealized = 0.0
    for row in rows:
        ticker = row["ticker"]
        qty = float(row["quantity"])
        avg_cost = float(row["avg_cost"])
        current_price = price_cache.get_price(ticker)
        cost_basis = qty * avg_cost
        if current_price is None:
            market_value = cost_basis
            unrealized = 0.0
            pct = 0.0
        else:
            market_value = qty * current_price
            unrealized = market_value - cost_basis
            pct = (unrealized / cost_basis * 100) if cost_basis else 0.0
        positions_value += market_value
        total_unrealized += unrealized
        positions.append(
            {
                "ticker": ticker,
                "quantity": round(qty, 6),
                "avg_cost": round(avg_cost, 2),
                "current_price": round(current_price, 2) if current_price is not None else None,
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pnl": round(unrealized, 2),
                "unrealized_pnl_percent": round(pct, 2),
            }
        )

    total_value = cash + positions_value
    return {
        "cash_balance": round(cash, 2),
        "positions": positions,
        "positions_value": round(positions_value, 2),
        "total_value": round(total_value, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
    }


def execute_trade(
    ticker: str,
    quantity: float,
    side: str,
    price_cache: PriceCache,
) -> dict:
    """Execute a market order. Returns a result dict. Raises TradeError on failure."""
    ticker = (ticker or "").strip().upper()
    side = (side or "").strip().lower()

    if not ticker:
        raise TradeError("Ticker is required.")
    if side not in {"buy", "sell"}:
        raise TradeError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise TradeError("Quantity must be a number.")
    if quantity <= 0:
        raise TradeError("Quantity must be positive.")

    price = price_cache.get_price(ticker)
    if price is None:
        raise TradeError(f"No live price available for {ticker}.")

    with get_connection() as conn:
        cash = float(
            conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?",
                (DEFAULT_USER_ID,),
            ).fetchone()["cash_balance"]
        )
        pos = conn.execute(
            "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
            (DEFAULT_USER_ID, ticker),
        ).fetchone()
        cur_qty = float(pos["quantity"]) if pos else 0.0
        cur_avg = float(pos["avg_cost"]) if pos else 0.0

        trade_value = quantity * price
        now = _now()

        if side == "buy":
            if trade_value > cash + _EPSILON:
                raise TradeError(
                    f"Insufficient cash: need ${trade_value:,.2f}, have ${cash:,.2f}."
                )
            new_cash = cash - trade_value
            new_qty = cur_qty + quantity
            # Weighted-average cost basis.
            new_avg = ((cur_qty * cur_avg) + trade_value) / new_qty
            _upsert_position(conn, ticker, new_qty, new_avg, now)
        else:  # sell
            if quantity > cur_qty + _EPSILON:
                raise TradeError(
                    f"Insufficient shares: trying to sell {quantity} {ticker}, "
                    f"own {cur_qty}."
                )
            new_cash = cash + trade_value
            new_qty = cur_qty - quantity
            if new_qty <= _EPSILON:
                conn.execute(
                    "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                    (DEFAULT_USER_ID, ticker),
                )
            else:
                # avg_cost unchanged when selling.
                _upsert_position(conn, ticker, new_qty, cur_avg, now)

        conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
            (new_cash, DEFAULT_USER_ID),
        )
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, side, quantity, price, now),
        )

    # Snapshot after the trade so the P&L chart reflects it immediately.
    record_snapshot(price_cache)

    return {
        "ticker": ticker,
        "side": side,
        "quantity": round(quantity, 6),
        "price": round(price, 2),
        "trade_value": round(trade_value, 2),
        "cash_balance": round(new_cash, 2),
        "executed_at": now,
    }


def _upsert_position(conn, ticker: str, qty: float, avg_cost: float, now: str) -> None:
    conn.execute(
        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(user_id, ticker) DO UPDATE SET "
        "quantity = excluded.quantity, avg_cost = excluded.avg_cost, "
        "updated_at = excluded.updated_at",
        (str(uuid.uuid4()), DEFAULT_USER_ID, ticker, qty, avg_cost, now),
    )


def record_snapshot(price_cache: PriceCache) -> float:
    """Persist the current total portfolio value and return it."""
    snapshot = get_portfolio(price_cache)
    total_value = snapshot["total_value"]
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), DEFAULT_USER_ID, total_value, _now()),
        )
    return total_value


def get_history(limit: int = 1000) -> list[dict]:
    """Return portfolio value snapshots oldest-first (for the P&L chart)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id = ? ORDER BY recorded_at DESC LIMIT ?",
            (DEFAULT_USER_ID, limit),
        ).fetchall()
    rows = list(reversed(rows))
    return [
        {"total_value": round(float(r["total_value"]), 2), "recorded_at": r["recorded_at"]}
        for r in rows
    ]
