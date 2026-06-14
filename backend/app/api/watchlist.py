"""Watchlist API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_market_source, get_price_cache
from app.market import MarketDataSource, PriceCache
from app.services import watchlist as watchlist_svc

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    ticker: str


@router.get("")
def get_watchlist(cache: PriceCache = Depends(get_price_cache)) -> dict:
    return {"watchlist": watchlist_svc.list_watchlist(cache)}


@router.post("")
async def add_ticker(
    req: AddTickerRequest,
    source: MarketDataSource = Depends(get_market_source),
    cache: PriceCache = Depends(get_price_cache),
) -> dict:
    try:
        ticker = await watchlist_svc.add_ticker(req.ticker, source)
    except watchlist_svc.WatchlistError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"added": ticker, "watchlist": watchlist_svc.list_watchlist(cache)}


@router.delete("/{ticker}")
async def remove_ticker(
    ticker: str,
    source: MarketDataSource = Depends(get_market_source),
    cache: PriceCache = Depends(get_price_cache),
) -> dict:
    try:
        removed = await watchlist_svc.remove_ticker(ticker, source)
    except watchlist_svc.WatchlistError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"removed": removed, "watchlist": watchlist_svc.list_watchlist(cache)}
