# Market Simulator Design

How FinAlly simulates realistic, live-feeling stock prices when no `MASSIVE_API_KEY` is
configured (the default). The simulator is the **fallback data source** behind the unified
interface — see `MARKET_INTERFACE.md` for how it plugs in, and `MASSIVE_API.md` for the
real-data alternative.

> **Status: built & tested.** Documents the as-built code in
> `backend/app/market/simulator.py` and `backend/app/market/seed_prices.py`
> (`test_simulator.py` + `test_simulator_source.py`, 27 tests).

---

## 1. Approach: Geometric Brownian Motion

The simulator evolves each price with **Geometric Brownian Motion (GBM)** — the same model
underpinning Black-Scholes. It's the right choice because GBM prices:

- **never go negative** (the update is multiplicative via `exp(...)`),
- are **lognormally distributed** (matches real equity returns),
- evolve **continuously** with tunable drift and volatility.

Updates run every **~500ms**, producing a steady stream of small moves that feel alive in
the UI (green/red flashes, filling sparklines) with **no external dependencies** — it's an
in-process asyncio task.

### Two classes, one responsibility each

- **`GBMSimulator`** — pure price math. Holds current prices and per-ticker params, exposes
  `step()`, `add_ticker()`, `remove_ticker()`, `get_price()`, `get_tickers()`. No async, no
  cache, no I/O — trivially unit-testable.
- **`SimulatorDataSource`** — the `MarketDataSource` adapter. Owns the asyncio loop that
  calls `step()` every 500ms and writes results into the `PriceCache`.

This split keeps the math deterministic and side-effect-free while the async/lifecycle
concerns live in the adapter.

---

## 2. The GBM step

At each tick a price evolves as:

```
S(t+dt) = S(t) · exp( (mu − σ²/2)·dt  +  σ·√dt·Z )
            └── drift ──┘   └─── diffusion (random) ───┘
```

| Symbol | Meaning | Example |
|--------|---------|---------|
| `S(t)` | current price | 190.00 |
| `mu`   | annualized drift (expected return) | 0.05 (5%) |
| `σ`    | annualized volatility | 0.22 (22%) |
| `dt`   | timestep as a fraction of a trading year | ~8.5e-8 |
| `Z`    | correlated standard-normal draw | N(0,1) |

**Choosing `dt`.** 500ms expressed against a trading year of 252 days × 6.5 h:

```
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600 = 5,896,800
dt = 0.5 / 5,896,800 ≈ 8.48e-8
```

This tiny `dt` yields **sub-cent moves per tick** that accumulate naturally — over a
simulated "day" a `σ=0.50` name (TSLA) traverses roughly the right intraday range.

```python
drift = (mu - 0.5 * sigma**2) * self._dt
diffusion = sigma * math.sqrt(self._dt) * z_correlated[i]
self._prices[ticker] *= math.exp(drift + diffusion)
```

---

## 3. Correlated moves (Cholesky)

Real stocks don't move independently — tech names rise and fall together. The simulator
draws **correlated** random shocks so the dashboard looks believable.

Given a correlation matrix `C`, compute `L = cholesky(C)`. For independent normals
`Z_ind`, the product `L @ Z_ind` is a correlated draw with covariance `C`:

```python
z_independent = np.random.standard_normal(n)
z_correlated  = self._cholesky @ z_independent if self._cholesky is not None else z_independent
```

**Correlation structure** (`seed_prices.py`):

| Relationship | ρ | Constant |
|--------------|---|----------|
| Same tech sector | 0.6 | `INTRA_TECH_CORR` |
| Same finance sector | 0.5 | `INTRA_FINANCE_CORR` |
| Cross-sector / unknown ticker | 0.3 | `CROSS_GROUP_CORR` |
| Anything with TSLA | 0.3 | `TSLA_CORR` — "it does its own thing" |

Groups: **tech** = {AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX}, **finance** = {JPM, V}.
TSLA is in the tech set but pinned to 0.3 with everything so it behaves independently.

The matrix is rebuilt (`_rebuild_cholesky`) whenever tickers are added/removed — O(n²) but
n is small (< 50). Cholesky requires a positive-semi-definite matrix, which a valid
correlation matrix guarantees.

---

## 4. Random "events" for drama

Each tick, every ticker has a small probability (`event_probability=0.001`) of a sudden
**2–5% shock** in a random direction — enough to keep the screen interesting:

```python
if random.random() < self._event_prob:
    shock_magnitude = random.uniform(0.02, 0.05)
    shock_sign = random.choice([-1, 1])
    self._prices[ticker] *= 1 + shock_magnitude * shock_sign
```

At 0.1% per ticker per tick, with 10 tickers at 2 ticks/sec, expect a notable move
**roughly every ~50 seconds** somewhere on the board.

---

## 5. Seed prices & per-ticker params

Realistic starting points and individualized volatility/drift so each name has its own
personality (`seed_prices.py`):

```python
SEED_PRICES = {
    "AAPL": 190.0, "GOOGL": 175.0, "MSFT": 420.0, "AMZN": 185.0, "TSLA": 250.0,
    "NVDA": 800.0, "META": 500.0, "JPM": 195.0, "V": 280.0, "NFLX": 600.0,
}

TICKER_PARAMS = {
    "AAPL": {"sigma": 0.22, "mu": 0.05},  "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT": {"sigma": 0.20, "mu": 0.05},  "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA": {"sigma": 0.50, "mu": 0.03},  # high vol
    "NVDA": {"sigma": 0.40, "mu": 0.08},  # high vol, strong drift
    "META": {"sigma": 0.30, "mu": 0.05},
    "JPM":  {"sigma": 0.18, "mu": 0.04},  "V": {"sigma": 0.17, "mu": 0.04},  # low vol
    "NFLX": {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS = {"sigma": 0.25, "mu": 0.05}   # for dynamically-added tickers
```

**Dynamically-added tickers** (not in the seed list) start at a random price in
**$50–$300** and use `DEFAULT_PARAMS`:

```python
self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))
```

> **Caveat for the LLM/UX layer:** in simulator mode an added `PYPL` gets a *fictional,
> random* price — not the real PYPL price. Fine for a sim, but the AI shouldn't reason about
> it as "fair value."

---

## 6. The hot path — `GBMSimulator.step()`

Called every 500ms; kept tight. Vectorizes the random draw, then loops per ticker to apply
GBM + the occasional shock, returning `{ticker: rounded_price}`.

```python
def step(self) -> dict[str, float]:
    n = len(self._tickers)
    if n == 0:
        return {}

    z_independent = np.random.standard_normal(n)
    z_correlated = self._cholesky @ z_independent if self._cholesky is not None else z_independent

    result = {}
    for i, ticker in enumerate(self._tickers):
        p = self._params[ticker]
        drift = (p["mu"] - 0.5 * p["sigma"]**2) * self._dt
        diffusion = p["sigma"] * math.sqrt(self._dt) * z_correlated[i]
        self._prices[ticker] *= math.exp(drift + diffusion)

        if random.random() < self._event_prob:                       # random event
            self._prices[ticker] *= 1 + random.uniform(0.02, 0.05) * random.choice([-1, 1])

        result[ticker] = round(self._prices[ticker], 2)
    return result
```

Add/remove rebuild the correlation matrix; `_add_ticker_internal` is the batch-init helper
that skips the rebuild so the constructor can add all tickers then rebuild once.

---

## 7. The async adapter — `SimulatorDataSource`

Wraps `GBMSimulator` in the `MarketDataSource` lifecycle and bridges it to the cache.

```python
async def start(self, tickers):
    self._sim = GBMSimulator(tickers=tickers, event_probability=self._event_prob)
    for ticker in tickers:                          # seed cache NOW → SSE has data instantly
        price = self._sim.get_price(ticker)
        if price is not None:
            self._cache.update(ticker=ticker, price=price)
    self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

async def _run_loop(self):
    while True:
        try:
            if self._sim:
                for ticker, price in self._sim.step().items():
                    self._cache.update(ticker=ticker, price=price)
        except Exception:
            logger.exception("Simulator step failed")     # a bad tick never kills the loop
        await asyncio.sleep(self._interval)               # default 0.5s
```

- `start` **seeds the cache immediately** so the cold-start `None` window (see
  `MARKET_INTERFACE.md` §4) is effectively zero in simulator mode.
- `add_ticker` adds to the sim **and** writes its seed price to the cache right away.
- `remove_ticker` removes from the sim and evicts from the cache.
- `stop` cancels the task and swallows `CancelledError` (idempotent).

---

## 8. Code structure

```
backend/app/market/
├── seed_prices.py    # SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS,
│                     # CORRELATION_GROUPS + correlation constants  (pure data)
└── simulator.py      # GBMSimulator (math)  +  SimulatorDataSource (async adapter)
```

Constants live apart from logic so prices/volatilities are tunable without touching the
engine, and the engine stays import-light and unit-testable.

---

## 9. Behavior notes

- Prices can't go negative — GBM is multiplicative and `exp()` is always positive.
- Tiny `dt` → sub-cent per-tick moves that accumulate; no artificial smoothing needed.
- The correlation matrix is always valid/PSD, so `np.linalg.cholesky` never raises.
- Rebuild on add/remove is O(n²); negligible for n < 50.
- Runs **24/7** — unlike real Massive data, the sim never goes flat off-hours, which is
  ideal for demos at any time of day.
- Determinism for tests: seed `random` and `numpy.random` to get reproducible paths.
