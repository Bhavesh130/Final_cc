"""Portfolio API routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_price_cache
from app.market import PriceCache
from app.services import portfolio as portfolio_svc

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    side: Literal["buy", "sell"]


@router.get("")
def get_portfolio(cache: PriceCache = Depends(get_price_cache)) -> dict:
    return portfolio_svc.get_portfolio(cache)


@router.post("/trade")
def execute_trade(
    req: TradeRequest, cache: PriceCache = Depends(get_price_cache)
) -> dict:
    try:
        result = portfolio_svc.execute_trade(req.ticker, req.quantity, req.side, cache)
    except portfolio_svc.TradeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    portfolio = portfolio_svc.get_portfolio(cache)
    return {"trade": result, "portfolio": portfolio}


@router.get("/history")
def get_history() -> dict:
    return {"snapshots": portfolio_svc.get_history()}
