"""Hot-stock ranking API."""
from __future__ import annotations

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from investment.data.hot_stocks import get_hot_stock_snapshot, rank_hot_stocks


router = APIRouter()


@router.get("/market/hot-stocks")
async def get_hot_stocks(
    market: Literal["CN", "HK", "US"] = "CN",
    mode: Literal["hot", "amount", "gainers"] = "hot",
    limit: int = Query(default=6, ge=1, le=20),
):
    try:
        snapshot = await asyncio.to_thread(get_hot_stock_snapshot, market)
        items = rank_hot_stocks(snapshot["rows"], mode=mode, limit=limit)
        return {
            "status": "ok",
            "result": {
                "market": market,
                "mode": mode,
                "generated_at": snapshot.get("generated_at"),
                "source": snapshot.get("source"),
                "stale": bool(snapshot.get("stale")),
                "items": items,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"{market} hot-stock data is unavailable") from exc
