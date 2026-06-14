# Market Data Interface

The unified Python API FinAlly uses to retrieve stock prices. **One abstract interface,
two implementations** — the Massive REST client when `MASSIVE_API_KEY` is set, the GBM
simulator otherwise. Everything downstream (SSE streaming, portfolio valuation, trade
fills) is **source-agnostic**: it reads from a shared in-memory `PriceCache` and never
talks to a data source directly.

> **Status: built & tested.** This documents the as-built code in
> `backend/app/market/` (8 modules, 73 passing tests). See `MARKET_DATA_SUMMARY.md` for the
> test/coverage breakdown, `MASSIVE_API.md` for the Massive REST details, and
> `MARKET_SIMULATOR.md` for the GBM internals.

---

## 1. Design at a glance

```
            create_market_data_source(cache)   ← reads MASSIVE_API_KEY
                          │
              ┌───────────┴────────────┐
              ▼                        ▼
   SimulatorDataSource          MassiveDataSource          (both: MarketDataSource ABC)
   GBM, ~500ms ticks            REST poll, 2–15s
              │                        │
              └────────► PriceCache ◄──┘     (thread-safe, single source of truth)
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
        SSE /api/stream  Portfolio      Trade
           /prices       valuation      fills
```

Key principles:
- **Producers write, consumers read.** Data sources only *push* into the cache; they never
  return prices to callers. This decouples the data origin from every consumer.
- **The cache is the only shared state.** It is the integration seam between the async
  producer task and the request handlers / SSE generators.
- **The source is chosen once at startup** by a factory and never again — no runtime
  branching on "are we simulating or live?" anywhere downstream.

### Module map (`backend/app/market/`)

| File | Exports | Role |
|------|---------|------|
| `models.py` | `PriceUpdate` | Immutable price snapshot (the only type that leaves the layer) |
| `cache.py` | `PriceCache` | Thread-safe store + version counter |
| `interface.py` | `MarketDataSource` | The ABC both sources implement |
| `simulator.py` | `SimulatorDataSource`, `GBMSimulator` | Default source |
| `massive_client.py` | `MassiveDataSource` | Real-data source |
| `seed_prices.py` | seed prices, GBM params, correlations | Simulator constants |
| `factory.py` | `create_market_data_source` | Env-driven selection |
| `stream.py` | `create_stream_router` | FastAPI SSE endpoint |

---

## 2. The data model — `PriceUpdate`

The single immutable structure that leaves the market layer. Frozen + `slots` for cheap,
safe sharing across threads.

```python
@dataclass(frozen=True, slots=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float = field(default_factory=time.time)   # Unix seconds

    @property
    def change(self) -> float: ...           # price - previous_price (rounded 4dp)
    @property
    def change_percent(self) -> float: ...   # %, guards divide-by-zero
    @property
    def direction(self) -> str: ...          # "up" | "down" | "flat"

    def to_dict(self) -> dict: ...           # JSON/SSE serialization
```

> `change` / `change_percent` / `direction` are **derived properties**, not stored fields —
> there is no way for them to drift out of sync with `price`. `to_dict()` is what the SSE
> layer serializes.

---

## 3. The abstract interface — `MarketDataSource`

```python
class MarketDataSource(ABC):
    @abstractmethod
    async def start(self, tickers: list[str]) -> None: ...
    @abstractmethod
    async def stop(self) -> None: ...
    @abstractmethod
    async def add_ticker(self, ticker: str) -> None: ...
    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None: ...
    @abstractmethod
    def get_tickers(self) -> list[str]: ...
```

Contract:
- `start(tickers)` — begin a background task that periodically writes to the cache. Called
  **exactly once**; calling twice is undefined.
- `stop()` — cancel the task and release resources. **Idempotent** (safe to call repeatedly).
- `add_ticker` / `remove_ticker` — mutate the active set; no-op if already in the desired
  state. `remove_ticker` also evicts the ticker from the cache.
- `get_tickers()` — current active set (sync; cheap).

The interface deliberately **returns no prices**. Prices flow out only through the cache.

---

## 4. The shared store — `PriceCache`

Thread-safe because a background producer thread and request-handler threads touch it
concurrently. A monotonic `version` counter is the mechanism the SSE layer uses to detect
"did anything change since I last sent?" without diffing.

```python
class PriceCache:
    def update(self, ticker, price, timestamp=None) -> PriceUpdate:
        with self._lock:
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price   # first tick → flat
            upd = PriceUpdate(ticker, round(price, 2), round(previous_price, 2),
                              timestamp or time.time())
            self._prices[ticker] = upd
            self._version += 1
            return upd

    def get(self, ticker)       -> PriceUpdate | None
    def get_price(self, ticker) -> float | None
    def get_all(self)           -> dict[str, PriceUpdate]   # shallow copy
    def remove(self, ticker)    -> None
    @property
    def version(self)           -> int
```

Notes:
- **First update for a ticker** sets `previous_price == price`, so `direction` is `"flat"`
  and `change` is `0` — no spurious flash on page load.
- `get_all()` returns a **shallow copy** so callers can iterate without holding the lock.
- Prices are rounded to **2 dp** on write (display-money precision).

### The cold-start `None` contract (important for downstream)

`get(ticker)` and `get_price(ticker)` return **`None`** for a ticker that hasn't ticked yet
— a real race on a fresh container before the first poll/step lands. Per the plan review
(item A2), consumers must define a rule. Recommended:

- **Trade fills:** if `get_price(ticker)` is `None`, reject the trade with a clear
  "price not available yet, try again in a moment" error rather than filling at 0.
- **Portfolio P&L:** treat a missing price as "unpriced" — show the position with a null/0
  unrealized P&L rather than crashing or implying a 100% loss.

Both source implementations mitigate this by **seeding the cache immediately** on `start`
(simulator) / doing an **immediate first poll** on `start` (Massive), so the window is small.

---

## 5. The factory — environment-driven selection

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        logger.info("Market data source: Massive API (real data)")
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    logger.info("Market data source: GBM Simulator")
    return SimulatorDataSource(price_cache=price_cache)
```

- Returns an **unstarted** source — the caller awaits `start(tickers)`.
- `.strip()` means a present-but-blank `MASSIVE_API_KEY=` falls through to the simulator
  (matches the plan's env-var semantics exactly).

---

## 6. The two implementations (summary)

Both wrap a producer in an asyncio background task and write `PriceUpdate`s into the cache.
They differ only in *where prices come from* and *how often*.

| | `SimulatorDataSource` | `MassiveDataSource` |
|---|---|---|
| Source | In-process GBM (`GBMSimulator`) | Massive REST snapshot poll |
| Cadence | ~500ms (`update_interval=0.5`) | 2–15s (`poll_interval=15.0` default) |
| Network | None | One `get_snapshot_all` call per cycle |
| Blocking | Pure CPU, trivial | Sync client wrapped in `asyncio.to_thread` |
| Cold start | Seeds cache from seed prices on `start` | Immediate first poll on `start` |
| `add_ticker` | Rebuilds correlation matrix, seeds price now | Appends to polled set (priced next poll) |

```python
# SimulatorDataSource core loop
async def _run_loop(self) -> None:
    while True:
        try:
            if self._sim:
                for ticker, price in self._sim.step().items():
                    self._cache.update(ticker=ticker, price=price)
        except Exception:
            logger.exception("Simulator step failed")   # never kill the loop
        await asyncio.sleep(self._interval)
```

See `MARKET_SIMULATOR.md` for the GBM math and `MASSIVE_API.md` §5 for the poll loop.

---

## 7. SSE streaming — `create_stream_router`

The cache's `version` counter drives change-detection so we only serialize/send when prices
actually changed.

```python
async def _generate_events(price_cache, request, interval=0.5):
    yield "retry: 1000\n\n"                 # browser auto-reconnect hint
    last_version = -1
    while True:
        if await request.is_disconnected():
            break
        if price_cache.version != last_version:
            last_version = price_cache.version
            prices = price_cache.get_all()
            if prices:
                data = {t: u.to_dict() for t, u in prices.items()}
                yield f"data: {json.dumps(data)}\n\n"
        await asyncio.sleep(interval)
```

- **One combined event per tick** — a `{ticker: {...}, ...}` map, not one event per ticker
  (plan review B3). The frontend reducer consumes this shape directly.
- Endpoint: `GET /api/stream/prices`, `media_type="text/event-stream"`.
- `retry: 1000` + `EventSource`'s built-in reconnect handle resilience.

---

## 8. Lifecycle & wiring (FastAPI)

```python
# startup
cache = PriceCache()
source = create_market_data_source(cache)            # picks Massive or simulator
await source.start(initial_tickers)                  # watchlist ∪ open positions
app.include_router(create_stream_router(cache))

# watchlist / positions change
await source.add_ticker("TSLA")
await source.remove_ticker("GOOGL")

# reads (request handlers)
price  = cache.get_price("AAPL")     # float | None  → trade fills, P&L
update = cache.get("AAPL")           # PriceUpdate | None
allp   = cache.get_all()             # dict[str, PriceUpdate]

# shutdown
await source.stop()
```

### Which tickers get priced? (plan review A3)

The priced set should be **watchlist ∪ open-position tickers** — a user can sell a ticker
off the watchlist while still holding it, and its price is still needed for P&L. The backend
owns this set and is responsible for calling `add_ticker` / `remove_ticker` to keep the
source's active set in sync as the watchlist and positions change.

---

## 9. Why this shape

| Decision | Rationale |
|----------|-----------|
| Strategy pattern behind one ABC | Swap simulator ↔ real data with zero downstream change |
| Push-to-cache, not pull-from-source | Decouples cadence from consumers; supports future multi-user |
| Cache `version` counter | O(1) change detection for SSE; no diffing |
| Immutable `PriceUpdate` | Safe to share across threads; derived fields can't desync |
| Sync Massive client in `to_thread` | Keeps the event loop responsive without an async HTTP client |
| Factory reads env once | No runtime "are we live?" branches scattered around |
