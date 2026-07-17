"""A-share hot ETF sector API."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from investment.data.etf_scanner import get_hot_etf_snapshot, rank_hot_etf_sectors


router = APIRouter()


@router.get("/etfs/hot-sectors")
async def get_hot_etf_sectors(limit: int = Query(default=10, ge=1, le=20)):
    try:
        snapshot = await asyncio.to_thread(get_hot_etf_snapshot)
        return {
            "status": "ok",
            "result": {
                "generated_at": snapshot.get("generated_at"),
                "source": snapshot.get("source"),
                "stale": bool(snapshot.get("stale")),
                "items": rank_hot_etf_sectors(snapshot["rows"], limit=limit),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail="A-share hot ETF data is unavailable") from exc
