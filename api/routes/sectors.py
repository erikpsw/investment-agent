"""Complete sector snapshot and on-demand trend routes."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from investment.data.sector_scanner import scan_sectors, sector_history


router = APIRouter()


@router.get("/sectors")
async def list_sectors():
    try:
        result = await asyncio.to_thread(scan_sectors)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"板块行情获取失败: {exc}") from exc
    return {
        "status": "ok",
        "result": {
            "generated_at": result["generated_at"],
            "sectors": result["rows"],
            "coverage_count": len(result["rows"]),
            "cached": result["cached"],
            "source": "东方财富沪深完整板块快照（10分钟缓存）",
        },
    }


@router.get("/sectors/{code}/history")
async def get_sector_history(code: str, days: int = Query(120, ge=30, le=250)):
    try:
        result = await asyncio.to_thread(sector_history, code, days)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"板块走势获取失败: {exc}") from exc
    return {"status": "ok", "result": result}
