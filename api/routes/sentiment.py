"""Broad-market quantitative sentiment API route."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from investment.data.market_sentiment import get_market_sentiment

router = APIRouter()


@router.get("/market/sentiment")
async def get_sentiment(refresh: bool = Query(default=False)):
    """Return CN / HK / US broad-market sentiment scores, resonance signals, and allocation guidance."""
    try:
        result = await asyncio.to_thread(get_market_sentiment, refresh)
        return {
            "status": "ok",
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Market sentiment data is temporarily unavailable",
        ) from exc
