"""Chat API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_market_source, get_price_cache
from app.market import MarketDataSource, PriceCache
from app.services import chat as chat_svc

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


@router.get("")
def get_history() -> dict:
    return {"messages": chat_svc.get_chat_history()}


@router.post("")
async def post_message(
    req: ChatRequest,
    cache: PriceCache = Depends(get_price_cache),
    source: MarketDataSource = Depends(get_market_source),
) -> dict:
    try:
        return await chat_svc.handle_chat(req.message, cache, source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
