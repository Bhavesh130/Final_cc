# Massive API Reference

Reference for the **Massive** market-data REST API as used in FinAlly for retrieving
**real-time** and **end-of-day** prices across **multiple tickers** in a single call.

> **What is Massive?** Massive (`massive.com`) is the rebrand of **Polygon.io**. The REST
> surface, response shapes, and the Python client are identical to Polygon's — old
> `polygon.io` doc URLs `301`-redirect to `massive.com`, and the Python package is
> published under both `massive` (current) and `polygon-api-client` (legacy). Anything
> written for the Polygon client works unchanged.

Verified against the live docs on 2026-06-12:
- Full market snapshot — `massive.com/docs/rest/stocks/snapshots/full-market-snapshot`
- Grouped daily (EOD) — `massive.com/docs/rest/stocks/aggregates/daily-market-summary`
- Python client — `github.com/massive-com/client-python`

---

## 1. Overview

| | |
|---|---|
| **Base URL** | `https://api.massive.com` (legacy `https://api.polygon.io` still works) |
| **Python package** | `pip install -U massive` (or legacy `pip install polygon-api-client`) |
| **Min Python** | 3.9+ |
| **Auth** | API key via `MASSIVE_API_KEY` env var, or `RESTClient(api_key=...)` |
| **Auth header** | `Authorization: Bearer <API_KEY>` — handled automatically by the client |
| **In FinAlly** | Selected only when `MASSIVE_API_KEY` is set and non-empty; otherwise the simulator runs (see `MARKET_INTERFACE.md`) |

### Plan tiers, data latency, and rate limits

This is the single most important operational detail and it is **not** about request
count alone — it is about **data latency**:

| Plan | Rate limit | Stock data latency |
|------|-----------|--------------------|
| Free / Starter / Developer | 5 req/min (free) | **15-minute delayed** |
| Advanced / Business | Unlimited (stay < ~100 req/s) | **Real-time** |

> On the free/developer tiers, `last_trade.price` is delayed by 15 minutes. FinAlly still
> works — prices just lag real wall-clock by 15 min. Genuine real-time requires Advanced
> or Business. The simulator (default) is always "live."

**Polling cadence in FinAlly:** free tier → poll every **15s**; paid tiers → every **2–5s**.
Because we fetch *all* watched tickers in one snapshot call, one poll = one request
regardless of watchlist size.

### Client initialization

```python
from massive import RESTClient

# Reads MASSIVE_API_KEY from the environment automatically
client = RESTClient()

# Or pass the key explicitly (how FinAlly does it)
client = RESTClient(api_key="your_key_here")
```

The `RESTClient` is **synchronous** and handles auth, request building, response parsing
into typed models, pagination, and retries (3 retries on 5xx by default). In FinAlly's async
backend we wrap calls in `asyncio.to_thread(...)` so they don't block the event loop.

---

## 2. Real-time prices for multiple tickers — Snapshot (primary endpoint)

The workhorse. Returns the current snapshot for **many tickers in one request**, which is
what keeps us inside the free-tier rate limit.

**REST**
```
GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,GOOGL,MSFT
```

**Query parameters**

| Param | Type | Notes |
|-------|------|-------|
| `tickers` | comma-separated list | **Case-sensitive.** Omit to get the entire market. |
| `include_otc` | boolean | Include OTC securities. Defaults to `false`. |

**Python client**
```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key="...")

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
)

for snap in snapshots:
    print(f"{snap.ticker}: ${snap.last_trade.price}")
    print(f"  Day change:  {snap.todays_change_percent:.2f}%")
    print(f"  Day OHLC:    O={snap.day.open} H={snap.day.high} "
          f"L={snap.day.low} C={snap.day.close}  V={snap.day.volume}")
    print(f"  Prev close:  {snap.prev_day.close}")
    print(f"  Trade ts:    {snap.last_trade.timestamp}")  # Unix ms
```

### Raw JSON vs. client attribute names

The wire format uses **abbreviated keys**; the Python client maps them to readable
attributes. Both are shown because you'll see the raw shape in network traces:

```json
{
  "ticker": "AAPL",
  "todaysChange": -4.54,
  "todaysChangePerc": -3.50,
  "updated": 1675190399999999999,
  "day":     { "o": 129.61, "h": 130.15, "l": 125.07, "c": 125.07, "v": 111237700, "vw": 127.35 },
  "lastTrade": { "p": 125.07, "s": 100, "x": 11, "t": 1675190399000 },
  "lastQuote": { "p": 125.06, "P": 125.08, "s": 500, "S": 1000, "t": 1675190399500 },
  "prevDay": { "o": 130.0, "h": 134.0, "l": 129.0, "c": 129.61, "v": 100000000, "vw": 131.0 }
}
```

| Raw key | Client attribute | Meaning |
|---------|------------------|---------|
| `lastTrade.p` | `snap.last_trade.price` | **Current/last traded price** ← FinAlly uses this |
| `lastTrade.t` | `snap.last_trade.timestamp` | Trade time, **Unix milliseconds** |
| `day.o/h/l/c/v` | `snap.day.open/high/low/close/volume` | Today's session OHLCV |
| `prevDay.c` | `snap.prev_day.close` | Previous close (for day-change calc) |
| `todaysChange` | `snap.todays_change` | Absolute change vs prev close |
| `todaysChangePerc` | `snap.todays_change_percent` | Percent change vs prev close |
| `updated` | `snap.updated` | Last update (Unix **nanoseconds**) |

> **Timestamp gotcha:** `last_trade.timestamp` is **milliseconds**, but `updated` is
> **nanoseconds**. FinAlly stores Unix **seconds** internally, so it divides
> `last_trade.timestamp` by 1000 (see `backend/app/market/massive_client.py`).

### Single-ticker snapshot (detail view)

For richer data on one ticker (e.g. when the user clicks it):

```python
snap = client.get_snapshot_ticker(
    market_type=SnapshotMarketType.STOCKS,
    ticker="AAPL",
)
print(snap.last_trade.price, snap.last_quote.bid_price, snap.last_quote.ask_price)
```

---

## 3. End-of-day prices for multiple tickers — Grouped Daily (the EOD endpoint)

For **end-of-day OHLCV across the entire US market in one request**, use **Grouped Daily**.
This is the correct EOD-for-many-tickers endpoint (do **not** loop per-ticker calls).

**REST**
```
GET /v2/aggs/grouped/locale/us/market/stocks/{date}?adjusted=true
```

**Parameters**

| Param | Type | Notes |
|-------|------|-------|
| `date` | required, `YYYY-MM-DD` | The trading date. Weekends/holidays return empty. |
| `adjusted` | optional boolean | Split-adjusted prices. Defaults to `true`. |

**Python client**
```python
bars = client.get_grouped_daily_aggs(date="2024-01-31", adjusted=True)

# Filter to the tickers we care about
watched = {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"}
for bar in bars:
    if bar.ticker in watched:
        print(f"{bar.ticker}: close=${bar.close} "
              f"O={bar.open} H={bar.high} L={bar.low} V={bar.volume} VWAP={bar.vwap}")
```

**Returned fields per ticker** (raw → client):

| Raw | Client | Meaning |
|-----|--------|---------|
| `T` | `bar.ticker` | Symbol |
| `o` `h` `l` `c` | `bar.open` `high` `low` `close` | OHLC |
| `v` | `bar.volume` | Volume |
| `vw` | `bar.vwap` | Volume-weighted average price |
| `n` | `bar.transactions` | Trade count |
| `t` | `bar.timestamp` | Window start, Unix **ms** |

> One request returns **every** US ticker for that date — ideal for seeding realistic
> starting prices or backfilling a daily chart without burning rate limit. Filter
> client-side to the watchlist.

### Alternatives for EOD (single ticker)

- **Previous close** — `GET /v2/aggs/ticker/{ticker}/prev` →
  `client.get_previous_close_agg(ticker="AAPL")`. Returns the prior session's OHLCV for
  one ticker. Handy for a quick "last close" without a date.
- **Daily open/close** — `GET /v1/open-close/{ticker}/{date}` →
  `client.get_daily_open_close_agg(ticker="AAPL", date="2024-01-31")`. Open, close, high,
  low, after-hours, and pre-market for one ticker on one date.

```python
prev = client.get_previous_close_agg(ticker="AAPL")
for agg in prev:
    print(f"Prev close: ${agg.close}  (O={agg.open} H={agg.high} L={agg.low} V={agg.volume})")
```

---

## 4. Intraday history — Aggregates (bars)

Not used for live polling, but the path to a populated detail chart (the plan notes there
is no historical backfill today — this is how you'd add it).

**REST**
```
GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
```

```python
bars = []
for a in client.list_aggs(
    ticker="AAPL",
    multiplier=1,
    timespan="minute",      # second|minute|hour|day|week|month|quarter|year
    from_="2024-01-01",
    to="2024-01-31",
    limit=50000,            # client auto-paginates beyond this
):
    bars.append(a)
```

`list_aggs` returns an **iterator** and transparently paginates. Each bar exposes
`.open .high .low .close .volume .vwap .timestamp .transactions`.

---

## 5. How FinAlly uses Massive (as built)

The real implementation lives in **`backend/app/market/massive_client.py`** as
`MassiveDataSource` (a `MarketDataSource`). It runs one background poll loop:

1. On `start(tickers)`: construct `RESTClient(api_key=...)`, do an **immediate first poll**
   so the cache is warm, then start the loop.
2. Each cycle: call `get_snapshot_all(market_type=STOCKS, tickers=self._tickers)` once
   (wrapped in `asyncio.to_thread` so the sync client doesn't block the loop).
3. For each snapshot, write `last_trade.price` and `last_trade.timestamp / 1000` (ms→s)
   into the shared `PriceCache`.
4. Sleep `poll_interval` (default 15s) and repeat.
5. `add_ticker` / `remove_ticker` mutate the polled set; removal also evicts from cache.

```python
async def _poll_once(self) -> None:
    if not self._tickers or not self._client:
        return
    try:
        snapshots = await asyncio.to_thread(self._fetch_snapshots)
        for snap in snapshots:
            try:
                self._cache.update(
                    ticker=snap.ticker,
                    price=snap.last_trade.price,
                    timestamp=snap.last_trade.timestamp / 1000.0,  # ms -> s
                )
            except (AttributeError, TypeError) as e:
                logger.warning("Skipping snapshot for %s: %s",
                               getattr(snap, "ticker", "???"), e)
    except Exception as e:
        logger.error("Massive poll failed: %s", e)   # loop retries next interval

def _fetch_snapshots(self) -> list:
    return self._client.get_snapshot_all(
        market_type=SnapshotMarketType.STOCKS,
        tickers=self._tickers,
    )
```

> **Why per-snapshot `try/except`:** a ticker that hasn't traded yet (or an unknown symbol)
> can have a `None` `last_trade`; we skip it rather than fail the whole poll.

---

## 6. Error handling

The client raises on HTTP errors. The poll loop catches everything and retries on the next
interval — a transient failure must never kill the background task.

| Status | Cause | FinAlly behavior |
|--------|-------|------------------|
| 401 | Invalid/missing API key | Log error; cache stays empty; keep retrying |
| 403 | Plan lacks the endpoint | Log error; retry (operator must upgrade) |
| 429 | Rate limit exceeded | Log; back off via the normal interval |
| 5xx | Server error | Client auto-retries (3x); then loop retries |

---

## 7. Off-hours & staleness notes

- **Market closed:** `last_trade.price` reflects the last trade (may include after-hours).
  Prices simply stop moving outside session hours — expected, not a bug.
- **Pre-market / `day` reset:** the `day` object resets at the open; pre-market values may
  reflect the prior session.
- **Delayed tiers:** on free/developer plans every price is 15 minutes behind wall-clock.
- **Weekends/holidays:** grouped-daily returns an empty list for non-trading dates.

---

## 8. Quick reference

| Need | Endpoint | Client method |
|------|----------|---------------|
| Real-time, many tickers | `/v2/snapshot/locale/us/markets/stocks/tickers` | `get_snapshot_all(market_type, tickers)` |
| Real-time, one ticker | `/v2/snapshot/.../tickers/{ticker}` | `get_snapshot_ticker(market_type, ticker)` |
| **EOD, all tickers** | `/v2/aggs/grouped/locale/us/market/stocks/{date}` | `get_grouped_daily_aggs(date, adjusted)` |
| EOD, one ticker (prev) | `/v2/aggs/ticker/{ticker}/prev` | `get_previous_close_agg(ticker)` |
| EOD, one ticker (date) | `/v1/open-close/{ticker}/{date}` | `get_daily_open_close_agg(ticker, date)` |
| Intraday history | `/v2/aggs/ticker/{t}/range/...` | `list_aggs(...)` |

**Sources:**
- [Full market snapshot — massive.com docs](https://massive.com/docs/rest/stocks/snapshots/full-market-snapshot)
- [Grouped daily / daily market summary — massive.com docs](https://massive.com/docs/rest/stocks/aggregates/daily-market-summary)
- [massive-com/client-python (README)](https://github.com/massive-com/client-python)
