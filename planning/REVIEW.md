# Review of PLAN.md

Reviewer agent — 2026-06-12

This review focuses on implementation risks in `planning/PLAN.md`, checked
against the current repository state. The market-data subsystem exists and is
tested; the DB layer, portfolio/watchlist/chat APIs, frontend, Docker scripts,
and E2E stack are still planned work.

## Current Highest-Priority Feedback

1. **Define the priced ticker set as `watchlist ∪ open positions`.** The market
   interface says `remove_ticker()` also removes the ticker from `PriceCache`.
   If `DELETE /api/watchlist/{ticker}` calls it while the user still owns that
   ticker, portfolio valuation and P&L lose the current price. The plan should
   explicitly say the backend owns active-market subscriptions and only removes
   a ticker when it is neither watched nor held.

2. **Specify missing-price behavior before portfolio work starts.** `PriceCache`
   can return `None` on cold start, immediately after adding a ticker, for an
   invalid Massive symbol, or during stale/off-hours real-data operation. The
   plan needs a single rule for trades, valuation, and snapshots. Recommended:
   reject trade fills until a current price exists; return nullable current
   price/P&L fields for unpriced positions; skip or defer snapshots until prices
   are available.

3. **Normalize and validate ticker input.** `POST /api/watchlist`,
   `DELETE /api/watchlist/{ticker}`, `POST /api/portfolio/trade`, and
   LLM-emitted actions all accept tickers, but the plan does not define casing,
   whitespace handling, allowed characters, max length, or invalid-symbol
   behavior. At minimum, normalize to uppercase trimmed strings and reject
   malformed symbols consistently before touching the DB or market source.

4. **Add a read endpoint for persisted chat history or state that refresh clears
   the UI.** The plan creates `chat_messages` and says the chat panel has
   scrolling history, but Section 8 only defines `POST /api/chat`. If history is
   meant to survive refresh, add `GET /api/chat/history`; otherwise say the
   database history is only LLM context.

5. **Define the chat action result schema, including partial failure.** The LLM
   schema says what the model requests, but the API response/storage shape for
   executed actions is unspecified. The frontend and tests need statuses such as
   `executed` / `rejected`, fill price, and validation errors per trade or
   watchlist change.

6. **Make SQLite startup and transaction rules normative.** Initialize the DB in
   FastAPI lifespan before background tasks start. Enable `WAL` and a
   `busy_timeout`, and wrap trade execution in one transaction covering balance
   update, position update/delete, trade insert, and immediate snapshot. The
   current "startup or first request" wording can race the snapshot task.

7. **Resolve the Docker volume contradiction.** Section 11 uses a named volume
   (`finally-data:/app/db`), while the prose and directory tree describe a
   project-root `db/` bind mount. Pick one. For this course/demo repo, a bind
   mount (`./db:/app/db`) is easier to inspect and matches the documented tree.

8. **Update the SSE contract to match the built market stream.** The current
   stream emits one combined JSON map per event and only when the cache version
   changes. PLAN.md still contains per-ticker language in Section 6. Also add a
   heartbeat comment every 15-30s so idle Massive/off-hours streams survive
   proxies and cloud platforms.

9. **Specify the mock LLM contract.** The E2E test "AI chat (mocked): trade
   execution appears inline" is not deterministic until `LLM_MOCK=true` has a
   documented input-to-output mapping, such as keyword-triggered buy/sell/watch
   actions that still pass through the real server-side validators.

10. **Confirm structured-output support and fallback behavior for the selected
    OpenRouter/Cerebras model.** If schema-constrained output fails, the backend
    should retry once and then return a safe assistant message with no actions.
    Do not best-effort parse trades from free text.

11. **Clarify frontend expectations in Massive mode.** The simulator updates
    around 500ms, but Massive polling can be 15s or stale outside market hours.
    The frontend should treat tick cadence as source-dependent; sparklines and
    flash animations cannot assume a fixed 500ms update rate.

12. **Tighten trade math rules.** Define positive finite quantity validation,
    sell-to-zero deletion behavior, an epsilon for fractional holdings, and the
    average-cost formula. Sequential buys should recompute weighted average
    cost; sells should not change `avg_cost`.

## Lower-Priority Cleanup

- Collapse the connection indicator to connected/disconnected unless the plan
  defines a reliable `EventSource` reconnecting state.
- Remove the duplicate `## Project Specification` heading.
- Specify Buy/Sell button colors.
- Cap recent chat history included in prompts.
- Cap watchlist size and LLM actions per response.
- State `/api/health` semantics as process liveness unless a separate readiness
  endpoint is added.

---

## Prior Detailed Review

Reviewer agent — 2026-06-12

This is a fresh, comprehensive review of `planning/PLAN.md`. It builds on the
existing doc-review pass already embedded in **PLAN.md Section 13** and on the
prior `REVIEW.md`, and deliberately avoids re-stating points those already
cover. Where a prior point is confirmed or extended, it is noted as such.

Scope of the codebase today: only the **market-data subsystem** (`backend/app/market/`,
73 tests, complete) and the planning docs exist. Everything else — backend
portfolio/watchlist/chat APIs, the DB layer, the Next.js frontend, Docker,
scripts, and E2E tests — is still to be built. Findings are tagged accordingly:

- **[RESOLVED]** — already handled in the completed market layer.
- **[OPEN]** — affects remaining backend/frontend work.

Findings are grouped by category and ordered by impact within each group.

---

## 1. Internal Consistency & Contradictions

### 1.1 [OPEN] `remove_ticker` evicts from the cache, which silently breaks P&L for held-but-unwatched positions — High

This is the sharp, code-level edge of Section 13.A.3 and prior REVIEW item 2.
The interface contract is explicit (`interface.py`):

> `remove_ticker` — Remove a ticker from the active set. **Also removes the
> ticker from the PriceCache.**

So the moment the watchlist `DELETE /api/watchlist/{ticker}` handler calls
`source.remove_ticker(...)`, the price disappears from the cache and
`/api/portfolio` can no longer value that position. PLAN.md Section 8 lets a
user remove any watchlist ticker, and Section 2 explicitly allows holding a
position you no longer watch. These two facts plus the eviction behavior
guarantee a broken-P&L bug unless the backend spec states the rule:

- The market source's active set must be **watchlist ∪ open-position tickers**.
- `DELETE /api/watchlist/{ticker}` must **only** call `remove_ticker` when the
  ticker is not also an open position (and the sell handler must call
  `remove_ticker` only when both the position is fully closed *and* the ticker
  is not watched).

PLAN.md should name this set explicitly and assign ownership (the
portfolio/watchlist service, not the market layer) so two agents don't each
assume the other wires it.

### 1.2 [OPEN] Chat history is persisted but there is no endpoint to read it back — High

Section 7 defines a `chat_messages` table and Section 9 step 7 stores every
message, "to load recent conversation history" (step 2). But Section 8's Chat
API has only `POST /api/chat`. There is no `GET /api/chat/history`. On a browser
refresh the frontend (Section 10 "scrolling conversation history") has no way to
rehydrate the conversation, even though it is sitting in SQLite. Either add a
`GET /api/chat/history` (or `GET /api/chat`) endpoint, or explicitly state that
chat history is server-side-only context and the UI starts empty each load. The
former is almost certainly intended given the persistence design.

### 1.3 [OPEN] The `actions` payload shape is never defined — Medium

`chat_messages.actions` is "JSON — trades executed, watchlist changes made," and
Section 10 says the chat panel shows "Trade executions and watchlist changes
shown inline as confirmations." But neither the stored shape nor the
`POST /api/chat` response shape for `actions` is specified — including the
critical case of **partial success** (LLM requested 3 trades, 1 failed
validation). The response needs a defined structure, e.g.:

```json
{
  "message": "...",
  "actions": {
    "trades": [
      {"ticker":"AAPL","side":"buy","quantity":10,"status":"executed","price":190.2},
      {"ticker":"TSLA","side":"buy","quantity":50,"status":"rejected","error":"insufficient cash"}
    ],
    "watchlist_changes": [{"ticker":"PYPL","action":"add","status":"executed"}]
  }
}
```

Define it once so the backend, the frontend confirmation UI, and the E2E
assertions agree. (Extends prior REVIEW clarification on failed-action
persistence.)

### 1.4 [RESOLVED→DOC] SSE event shape in Section 6 still contradicts the built stream — Low (doc fix)

Section 6 says "Each SSE event contains ticker, price, previous price,
timestamp, and change direction" (per-ticker framing). The shipped `stream.py`
emits **one combined map per event**: `data: {"AAPL": {...}, "GOOGL": {...}}`,
version-gated. Section 13.B.3 already flags this as done, but the normative
Section 6 prose was never corrected and is what an implementer reads first.
Fix the Section 6 text to describe the combined-map payload and the
`to_dict()` field set (`ticker, price, previous_price, timestamp, change,
change_percent, direction`).

### 1.5 [OPEN] Section 11 internally contradicts itself on the volume — Medium

Confirmed (Section 13.A.9 / prior REVIEW item 7), restated here only because it
spans three artifacts: the `docker run` line uses a **named volume**
(`finally-data:/app/db`), the prose says the project-root `db/` **bind-mounts**
to `/app/db`, and Section 4's tree calls top-level `db/` "the volume mount
target" with a `.gitkeep`. A named volume never touches `db/.gitkeep`. Pick one
mechanism. Recommendation: bind-mount `./db:/app/db` so the SQLite file is
visible on the host (better for a teaching project) and update the run command,
scripts, and tree to match.

---

## 2. Gaps That Block an Implementer

### 2.1 [OPEN] No input validation / normalization rules for tickers — High

`POST /api/watchlist`, `DELETE /api/watchlist/{ticker}`, and
`POST /api/portfolio/trade` all take a `ticker`, but the plan never says how it
is validated or normalized. Open questions an implementer must guess at:

- Case/whitespace: is `" aapl "` normalized to `AAPL`? (Must be, or the
  `UNIQUE(user_id, ticker)` constraint and cache keys diverge — the simulator
  keys by the exact string passed.)
- Unknown symbols: in **simulator** mode any string gets a random price
  (`SEED_PRICES.get(ticker, random.uniform(50, 300))`), so `ZZZZ` "works" and is
  indistinguishable from a real ticker. In **Massive** mode an invalid symbol
  returns no data → cold-start-style missing price forever. The behavior
  diverges between the two sources and needs a defined contract (e.g. reject
  non-`[A-Z]{1,5}` symbols; in Massive mode reject symbols that return no quote
  within N polls).

This matters most for **AI-driven** adds, where the LLM may hallucinate tickers.

### 2.2 [OPEN] Missing-price / cold-start rule for trades, valuation, and snapshots — High

Confirmed open (Section 13.A.2, prior REVIEW item 1). Adding specifics the prior
notes didn't pin down:

- **Trade fill:** `get_price()` can return `None` on a fresh container before
  the first tick, or right after an AI-added ticker, or off-hours in Massive
  mode. Define the rule: reject with `409`/`422` and a clear message until a
  price exists. Do **not** fill at `0` or seed price silently.
- **Valuation:** `/api/portfolio` must define per-position behavior when price is
  `None` — emit `current_price: null`, `unrealized_pnl: null` and exclude that
  position from `total_value` (and say so), rather than treating it as `0`.
- **Snapshots:** the 30s `portfolio_snapshots` task computes `total_value`, which
  depends on prices. State that snapshots are skipped (or use last-known price)
  until at least one tick exists, so the very first snapshot isn't garbage.

### 2.3 [OPEN] Sell-to-zero: delete the position row or keep a zero-quantity row? — Medium

Section 2 says selling makes a position "update or disappear," but the schema
has `UNIQUE(user_id, ticker)` and no soft-delete column. Specify that a sell
reducing quantity to 0 (within a float epsilon) **deletes** the row, and define
the float-epsilon threshold (tie-in with the Section 13.C.4 float-money note).
Also specify whether selling the entire position then triggers `remove_ticker`
(see 1.1). Without this, "disappear" is ambiguous and the positions table /
heatmap may show ghost zero-weight tiles.

### 2.4 [OPEN] Trade quantity validation is unspecified — Medium

`POST /api/portfolio/trade` takes `{ticker, quantity, side}` but no constraints.
Define: quantity must be a positive finite number; reject `0`, negatives,
`NaN`/`Inf`, and non-numeric. State whether there is a max (a fractional-share
sim could accept `quantity: 1e308`). The same validation must apply to
LLM-emitted trades (Section 9), where malformed numbers are likeliest.

### 2.5 [OPEN] Initial portfolio snapshot at startup — Medium

Prior REVIEW raised this; restating as a concrete gap: the P&L chart
(`GET /api/portfolio/history`) is empty for up to 30s after boot because the
first snapshot is on a 30s timer. Spec an immediate snapshot at startup (after
the first price tick is available — see 2.2) so the chart has a baseline point
on first load. Also define what `/api/portfolio/history` returns with zero
snapshots: `[]`, not an error.

### 2.6 [OPEN] No SSE heartbeat / keep-alive defined — Medium

The stream is **version-gated**: it yields only when `price_cache.version`
changes. In **simulator** mode prices move every 500ms so this is moot. But in
**Massive** mode off-hours (Section 13.C.3), prices are flat → the cache version
never advances → the endpoint sends nothing for long stretches. Idle HTTP
connections through proxies/load balancers (App Runner, Render — Section 11) are
commonly killed after 30–120s of silence, which will look like a disconnect to
the user. Recommend a periodic comment heartbeat (`: keep-alive\n\n`) every
~15–30s regardless of version change. This is a market-layer change, so flag it
explicitly even though the layer is "complete."

### 2.7 [OPEN] Conversation-history cap is still a TODO — Low

Section 13.A.8 / prior REVIEW already flag the unbounded prompt. Pick a number
in the plan (e.g. last 20 messages or ~4k tokens) so the chat agent isn't left
to invent one. Not a blocker, but trivially closeable now.

---

## 3. Architectural & Correctness Risks

### 3.1 [OPEN] Race between the 500ms SSE cadence and the multi-second Massive poll — Medium

The SSE loop sleeps 500ms and re-emits whenever `version` changed. The Massive
poller updates every 2–15s. Between polls the version is stable, so the stream
correctly stays quiet — fine. The real risk is the **frontend** assuming ~500ms
ticks (sparkline accumulation, flash animations) and behaving oddly when ticks
arrive every 15s in Massive mode (sparklines barely move; flashes are rare).
PLAN.md should note that tick cadence is source-dependent and the frontend must
not assume a fixed interval.

### 3.2 [OPEN] SQLite concurrency contract — Medium

Confirmed (Section 13.B.4, prior REVIEW item 6). Make it normative in Section 7,
not just a suggestion: `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`,
and a single transaction wrapping the read-balance → validate → write-position →
write-trade → write-snapshot sequence so a failed trade can't leave a partial
state. With a background snapshot task + (in sim mode) request handlers all
touching one file, the default rollback-journal mode will produce intermittent
`database is locked`.

### 3.3 [OPEN] Lazy init "on first request" races the background tasks — Medium

Section 7 says the DB is initialized "on startup (or first request)." The
background snapshot task and the market source start at app startup. If init is
deferred to first request, the snapshot task may run (and try to write
`portfolio_snapshots`) before the schema exists. Resolve to **init at startup
(lifespan/startup event), before launching background tasks** — and drop the
"or first request" ambiguity. This also fixes the order-of-operations for 2.2.

### 3.4 [OPEN] `avg_cost` recomputation correctness on sequential buys — Medium

Section 13.C.4 flags float display; the deeper correctness point: average cost
must be recomputed as a share-weighted average across buys
(`new_avg = (old_qty*old_avg + buy_qty*price) / (old_qty + buy_qty)`), and a
**sell must not change `avg_cost`** (only realized P&L, which isn't even stored).
State this formula in Section 7 so every agent computes P&L consistently and
the LLM context numbers match the positions table.

### 3.5 [OPEN] `/api/health` semantics undefined — Low

Section 11 relies on `/api/health` for Docker/deployment health checks but
Section 8 only labels it "Health check." Define what it verifies: liveness only
(always `200` if the process is up) vs. readiness (DB reachable + market source
running + at least one price cached). For container orchestration, a readiness
check that fails until the first tick can cause boot loops — recommend a simple
liveness `200 {"status":"ok"}` and keep readiness out of it.

---

## 4. Security & Robustness

### 4.1 [OPEN] Prompt-injection / unbounded agency via auto-executed trades — Medium

Section 9 auto-executes LLM-emitted trades with no confirmation. Within a
fake-money single-user sim the *financial* stakes are zero (correctly noted),
but two robustness concerns remain: (a) a user message can instruct the model to
spam adds or churn trades; (b) the model can emit many trades/watchlist changes
in one turn. Recommend documented guardrails: a per-response cap (e.g. ≤ N
trades, ≤ N watchlist changes), and server-side validation as the source of
truth regardless of what the model returns (already implied by "same validation
as manual trades" — make it explicit that the **server**, not the model, decides
fills).

### 4.2 [OPEN] LLM structured-output reliability + fallback still unspecified — High

Confirmed (Section 13.A.6, prior REVIEW item 3). Beyond confirming the
provider/model honors `response_format`, the plan needs a concrete
malformed-response policy: retry once with a stricter instruction, then on
failure return a safe `message` with empty `trades`/`watchlist_changes` and
**never** partially-parse a trade out of free text. Note also that the model id
`openrouter/openai/gpt-oss-120b` and the "cerebras-inference skill" referenced in
Section 9 should be reconciled with the actual skill available in this repo
(`cerebras`) — the names differ and an implementer following Section 9 verbatim
will look for a skill that isn't named that.

### 4.3 [OPEN] No rate limiting / size limits on `/api/chat` and watchlist — Low

Single-user and local, so low priority, but a runaway frontend (or a deployed
demo) can hammer the LLM endpoint and rack up OpenRouter cost. A note that chat
is best-effort and unthrottled (acceptable) — or a minimal debounce on the
frontend send button — closes the loop. Also cap watchlist size (e.g. ≤ 50) so
an AI add-loop can't unboundedly grow the priced set and the Massive poll.

---

## 5. Testability

### 5.1 [OPEN] `LLM_MOCK` contract is undefined — High (blocks an E2E scenario)

Confirmed (Section 13.A.5, prior REVIEW item 4). The "AI chat (mocked): trade
execution appears inline" E2E test is unwritable until the mock's
input→output mapping is specified. Define it concretely, e.g.:

- message contains `buy` → `{trades:[{ticker:"AAPL",side:"buy",quantity:1}]}`
- message contains `sell` → a fixed sell of a held position
- message contains `watch` → a fixed watchlist add/remove
- otherwise → analysis-only, no actions

And ensure the mock path **still runs server-side trade validation**, so the
E2E can also assert the insufficient-funds rejection path deterministically.

### 5.2 [OPEN] SSE-resilience E2E is hard to drive deterministically — Medium

The "disconnect and verify reconnection" scenario depends on
`EventSource` auto-retry and the `retry: 1000` directive. Playwright can't
easily force a mid-stream server drop without infra help. Specify the mechanism:
e.g. an offline toggle via `context.setOffline(true/false)`, or a test-only
endpoint that closes streams, plus the exact UI assertion (the connection dot
goes red then green). Tie this to the connection-state mapping decision (item
6.1 below) so the assertion target is unambiguous.

### 5.3 [OPEN] Cold-start determinism for fresh-start E2E — Low

"Fresh start: prices are streaming" can flake if the first tick hasn't landed
when the assertion runs. Note that tests should wait for the first SSE payload
(or first non-empty watchlist price) rather than a fixed timeout — especially
relevant given the missing-price rules in 2.2.

---

## 6. Simplification Opportunities

### 6.1 [OPEN] Collapse the connection indicator to two states — Medium

Confirmed (Section 13.A.7/B.1, prior REVIEW clarification). `EventSource`
cleanly exposes only `onopen` and `onerror`; "reconnecting" vs "disconnected" is
guesswork via `readyState`. Recommend green (`onopen`) / red (`onerror`) and
delete the yellow state from Section 2's visual spec so the frontend agent and
the E2E assertion (5.2) have one unambiguous target.

### 6.2 [OPEN] Drop `docker-compose.yml` as a second launch path — Low

Confirmed (Section 13.B.5, prior REVIEW Minor). If `scripts/start_*` wrapping
`docker run` is canonical, the optional compose file is a drift risk for
two-launch-path skew. Keep only the test compose (`docker-compose.test.yml`).

### 6.3 [OPEN] State the "no cached aggregates" boundary — Low

Confirmed (Section 13.B.2). Make it normative: the **only** persisted aggregate
is `portfolio_snapshots`; `total_value`, P&L, and weights are always derived
live from `positions` + price cache. Prevents an agent from caching a running
total that drifts.

### 6.4 [OPEN] Single source of truth for the default ticker list — Low

The 10 default tickers are listed in PLAN.md Section 7, in `backend/CLAUDE.md`,
and in `seed_prices.py`. The DB-seed logic (still to build) should import the
list from the market layer rather than hardcode an 11th copy, so they can't
drift.

---

## 7. Minor / Nits

These are confirmed from Section 13.C and the prior REVIEW; listed for
completeness, none are blockers:

- **Stray heading:** remove `## Project Specification` (line 3) above `## 1. Vision`.
- **Buy/Sell button colors:** specify Buy=green / Sell=red vs. purple submit.
- **Massive off-hours staleness:** add the one-line "prices just don't move, not a bug" note (and see the heartbeat interaction in 2.6).
- **Float money display:** round currency in API responses / UI to avoid `$9999.9999998`.
- **Skill name mismatch:** Section 9 says "cerebras-inference skill"; the repo skill is `cerebras`. Reconcile.

---

## Summary of Highest-Impact Items

1. `remove_ticker` cache eviction silently breaks P&L for held-but-unwatched positions — define the **watchlist ∪ positions** priced set and gate removal (1.1).
2. No endpoint to read back persisted chat history (1.2).
3. Missing-price/cold-start rules for trades, valuation, and snapshots — define reject vs. null behavior (2.2).
4. Ticker validation/normalization undefined and divergent between sim and Massive modes (2.1).
5. LLM structured-output reliability + malformed-response fallback unspecified; skill-name mismatch (4.2).
6. `LLM_MOCK` input→output contract undefined, blocking the chat E2E (5.1).
7. SQLite WAL + single-transaction trade boundary should be normative, and DB init must precede background tasks (3.2, 3.3).
8. Volume mechanism (named vs. bind) self-contradicts across run command, prose, and tree (1.5).
9. No SSE heartbeat → off-hours/idle connections look dead behind proxies (2.6).
10. `actions` payload + partial-success shape undefined for chat response and storage (1.3).
