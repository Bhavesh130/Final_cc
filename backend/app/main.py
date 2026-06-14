"""FastAPI application entrypoint.

Wires together the market data source, REST + SSE routers, background portfolio
snapshotting, and static frontend serving — all on a single port.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from app.api import chat as chat_api
from app.api import health as health_api
from app.api import portfolio as portfolio_api
from app.api import watchlist as watchlist_api
from app.config import get_static_dir
from app.db import get_connection, init_db
from app.market import PriceCache, create_market_data_source
from app.services import portfolio as portfolio_svc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL = 30.0  # seconds (PLAN §7)


def _startup_tickers() -> list[str]:
    """Union of watchlist tickers and tickers backing open positions."""
    init_db()
    with get_connection() as conn:
        wl = [r["ticker"] for r in conn.execute("SELECT ticker FROM watchlist")]
        pos = [r["ticker"] for r in conn.execute("SELECT ticker FROM positions")]
    # Preserve order, de-dupe.
    seen: dict[str, None] = {}
    for t in [*wl, *pos]:
        seen.setdefault(t, None)
    return list(seen)


async def _snapshot_loop(cache: PriceCache) -> None:
    """Periodically record total portfolio value for the P&L chart."""
    while True:
        try:
            await asyncio.sleep(SNAPSHOT_INTERVAL)
            await asyncio.to_thread(portfolio_svc.record_snapshot, cache)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Snapshot loop iteration failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    source = create_market_data_source(cache)
    tickers = _startup_tickers()
    await source.start(tickers)

    # Initial snapshot so the P&L chart has a starting point.
    await asyncio.to_thread(portfolio_svc.record_snapshot, cache)

    snapshot_task = asyncio.create_task(_snapshot_loop(cache), name="snapshot-loop")

    app.state.price_cache = cache
    app.state.market_source = source
    logger.info("FinAlly started with %d tickers", len(tickers))

    try:
        yield
    finally:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except asyncio.CancelledError:
            pass
        await source.stop()
        logger.info("FinAlly stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="FinAlly", version="0.1.0", lifespan=lifespan)

    # API routers.
    app.include_router(health_api.router)
    app.include_router(portfolio_api.router)
    app.include_router(watchlist_api.router)
    app.include_router(chat_api.router)

    # SSE streaming. The stream router reads from app.state at request time.
    @app.get("/api/stream/prices")
    async def stream_prices(request: Request):
        from app.market.stream import _generate_events

        return StreamingResponse(
            _generate_events(request.app.state.price_cache, request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the Next.js static export with SPA fallback to index.html."""
    static_dir = get_static_dir()

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):  # noqa: ANN001
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)

        if not static_dir.exists():
            return JSONResponse(
                {"detail": "Frontend not built. Run the frontend build."},
                status_code=503,
            )

        candidate = (static_dir / full_path).resolve()
        # Prevent path traversal outside the static dir.
        if static_dir.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)

        # Next.js export emits <route>.html files; try that too.
        html_candidate = (static_dir / f"{full_path}.html").resolve()
        if static_dir.resolve() in html_candidate.parents and html_candidate.is_file():
            return FileResponse(html_candidate)

        index = static_dir / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"detail": "Not found"}, status_code=404)


app = create_app()
