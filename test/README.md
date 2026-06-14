# FinAlly E2E Tests (Playwright)

End-to-end browser tests covering the key user flows: fresh-start watchlist +
streaming prices, watchlist add/remove, buying shares, and the (mocked) AI chat
executing an inline trade.

## Run against a local app

Start the app with the LLM mocked, then run the tests:

```bash
# Terminal 1 — run the app (from repo root)
LLM_MOCK=true ./scripts/start_mac.sh        # or docker compose up --build

# Terminal 2 — run the tests
cd test
npm install
npm run install:browsers
BASE_URL=http://localhost:8000 npm test
```

## Run fully containerized

Spins up the app container (LLM mocked) and a Playwright container together:

```bash
docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit
```

The Playwright service waits for the app's `/api/health` check, then runs the
suite against `http://app:8000`.
