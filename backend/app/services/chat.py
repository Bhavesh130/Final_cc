"""LLM chat service.

Builds portfolio context, calls the LLM (Cerebras via LiteLLM/OpenRouter) with
structured outputs, auto-executes any trades and watchlist changes it returns,
persists the conversation, and returns the assembled response.

When LLM_MOCK is enabled the LLM call is replaced by a deterministic parser so
the app runs (and E2E tests pass) without network access or an API key.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from app.config import DEFAULT_USER_ID, get_openrouter_api_key, llm_mock_enabled
from app.db import get_connection
from app.market import MarketDataSource, PriceCache
from app.services import portfolio as portfolio_svc
from app.services import watchlist as watchlist_svc

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}
_HISTORY_LIMIT = 10

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant embedded in a simulated \
trading workstation. The user trades a virtual $10,000 portfolio (fake money, market \
orders only, instant fills).

Your job:
- Analyze portfolio composition, risk concentration, and P&L.
- Suggest trades with concise, data-driven reasoning.
- Execute trades when the user asks or agrees — put them in the `trades` array.
- Manage the watchlist proactively via `watchlist_changes`.
- Be concise. Reference real numbers from the provided context.

You MUST respond with valid JSON matching the required schema. The `message` field \
is your conversational reply shown to the user. Only include trades/watchlist_changes \
you actually intend to execute now."""


class TradeInstruction(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


class WatchlistChange(BaseModel):
    ticker: str
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    message: str
    trades: list[TradeInstruction] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Persistence helpers
# --------------------------------------------------------------------------- #
def _store_message(role: str, content: str, actions: dict | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                DEFAULT_USER_ID,
                role,
                content,
                json.dumps(actions) if actions is not None else None,
                _now(),
            ),
        )


def get_chat_history(limit: int = 100) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content, actions, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (DEFAULT_USER_ID, limit),
        ).fetchall()
    rows = list(reversed(rows))
    return [
        {
            "role": r["role"],
            "content": r["content"],
            "actions": json.loads(r["actions"]) if r["actions"] else None,
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def _recent_history_messages() -> list[dict]:
    """Recent turns formatted as OpenAI-style chat messages."""
    history = get_chat_history(limit=_HISTORY_LIMIT)
    return [{"role": h["role"], "content": h["content"]} for h in history]


# --------------------------------------------------------------------------- #
# Context
# --------------------------------------------------------------------------- #
def _build_context(price_cache: PriceCache) -> str:
    pf = portfolio_svc.get_portfolio(price_cache)
    wl = watchlist_svc.list_watchlist(price_cache)

    lines = [
        f"Cash balance: ${pf['cash_balance']:,.2f}",
        f"Total portfolio value: ${pf['total_value']:,.2f}",
        f"Total unrealized P&L: ${pf['total_unrealized_pnl']:,.2f}",
        "",
        "Positions:",
    ]
    if pf["positions"]:
        for p in pf["positions"]:
            lines.append(
                f"  {p['ticker']}: {p['quantity']} @ avg ${p['avg_cost']:.2f}, "
                f"now ${p['current_price']}, P&L ${p['unrealized_pnl']:.2f} "
                f"({p['unrealized_pnl_percent']:+.2f}%)"
            )
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("Watchlist (live prices):")
    for w in wl:
        price = f"${w['price']:.2f}" if w["price"] is not None else "n/a"
        lines.append(f"  {w['ticker']}: {price} ({w['change_percent']:+.2f}%)")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# LLM call
# --------------------------------------------------------------------------- #
def _call_llm(message: str, context: str) -> ChatResponse:
    """Blocking LLM call via LiteLLM → OpenRouter (Cerebras)."""
    from litellm import completion  # imported lazily to keep import cost off hot paths

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current portfolio context:\n{context}"},
        *_recent_history_messages(),
        {"role": "user", "content": message},
    ]
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
        api_key=get_openrouter_api_key(),
    )
    content = response.choices[0].message.content
    return ChatResponse.model_validate_json(content)


# --------------------------------------------------------------------------- #
# Mock mode
# --------------------------------------------------------------------------- #
_TRADE_RE = re.compile(
    r"\b(buy|sell)\s+(\d+(?:\.\d+)?)?\s*(?:shares?\s+of\s+)?\$?([A-Za-z]{1,5})\b",
    re.IGNORECASE,
)
_WATCH_ADD_RE = re.compile(r"\b(?:add|watch)\s+\$?([A-Za-z]{1,5})\b", re.IGNORECASE)
_WATCH_REMOVE_RE = re.compile(
    r"\b(?:remove|unwatch|drop)\s+\$?([A-Za-z]{1,5})\b", re.IGNORECASE
)
_NOISE_WORDS = {"OF", "THE", "ME", "A", "TO", "MY", "ALL", "SOME"}


def _mock_response(message: str, price_cache: PriceCache) -> ChatResponse:
    trades: list[TradeInstruction] = []
    watchlist_changes: list[WatchlistChange] = []

    for side, qty, ticker in _TRADE_RE.findall(message):
        ticker = ticker.upper()
        if ticker in _NOISE_WORDS:
            continue
        quantity = float(qty) if qty else 1.0
        trades.append(
            TradeInstruction(ticker=ticker, side=side.lower(), quantity=quantity)
        )

    for ticker in _WATCH_ADD_RE.findall(message):
        ticker = ticker.upper()
        if ticker not in _NOISE_WORDS and not any(t.ticker == ticker for t in trades):
            watchlist_changes.append(WatchlistChange(ticker=ticker, action="add"))
    for ticker in _WATCH_REMOVE_RE.findall(message):
        ticker = ticker.upper()
        if ticker not in _NOISE_WORDS:
            watchlist_changes.append(WatchlistChange(ticker=ticker, action="remove"))

    pf = portfolio_svc.get_portfolio(price_cache)
    if trades or watchlist_changes:
        reply = "[mock] Got it — applying your requested actions now."
    else:
        reply = (
            f"[mock] Your portfolio is worth ${pf['total_value']:,.2f} "
            f"with ${pf['cash_balance']:,.2f} in cash and "
            f"{len(pf['positions'])} position(s). "
            "Ask me to buy or sell (e.g. 'buy 5 AAPL') and I'll execute it."
        )
    return ChatResponse(
        message=reply, trades=trades, watchlist_changes=watchlist_changes
    )


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
async def handle_chat(
    message: str,
    price_cache: PriceCache,
    source: MarketDataSource,
) -> dict:
    """Process a user chat message end-to-end. Returns the response payload."""
    import asyncio

    message = (message or "").strip()
    if not message:
        raise ValueError("Message cannot be empty.")

    _store_message("user", message)
    context = _build_context(price_cache)

    try:
        if llm_mock_enabled():
            result = _mock_response(message, price_cache)
        else:
            result = await asyncio.to_thread(_call_llm, message, context)
    except Exception:
        logger.exception("LLM call failed")
        fallback = "Sorry — I couldn't process that request right now. Please try again."
        _store_message("assistant", fallback)
        return {"message": fallback, "actions": {"trades": [], "watchlist_changes": []}}

    executed_trades = []
    for trade in result.trades:
        try:
            res = portfolio_svc.execute_trade(
                trade.ticker, trade.quantity, trade.side, price_cache
            )
            executed_trades.append({"status": "executed", **res})
        except portfolio_svc.TradeError as e:
            executed_trades.append(
                {
                    "status": "rejected",
                    "ticker": trade.ticker.upper(),
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "error": str(e),
                }
            )

    watchlist_results = []
    for change in result.watchlist_changes:
        try:
            if change.action == "add":
                t = await watchlist_svc.add_ticker(change.ticker, source)
            else:
                t = await watchlist_svc.remove_ticker(change.ticker, source)
            watchlist_results.append(
                {"status": "applied", "ticker": t, "action": change.action}
            )
        except watchlist_svc.WatchlistError as e:
            watchlist_results.append(
                {
                    "status": "rejected",
                    "ticker": change.ticker.upper(),
                    "action": change.action,
                    "error": str(e),
                }
            )

    actions = {"trades": executed_trades, "watchlist_changes": watchlist_results}
    _store_message("assistant", result.message, actions)
    return {"message": result.message, "actions": actions}
