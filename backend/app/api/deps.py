"""Shared FastAPI dependencies.

The price cache and market data source are created once during app startup and
stored on `app.state`. These accessors expose them to route handlers.
"""

from __future__ import annotations

from fastapi import Request

from app.market import MarketDataSource, PriceCache


def get_price_cache(request: Request) -> PriceCache:
    return request.app.state.price_cache


def get_market_source(request: Request) -> MarketDataSource:
    return request.app.state.market_source
