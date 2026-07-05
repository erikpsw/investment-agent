"""Complete sector snapshot and on-demand trend routes."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from investment.api.routes.formula_ranking import FORMULA_DESCRIPTION, FormulaMode, _rank_live_item
from investment.data.market_scanner import enrich_stock_history
from investment.data.sector_scanner import scan_sectors, sector_constituents, sector_history


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
            "source": result.get("source") or "沪深完整板块快照",
        },
    }


@router.get("/sectors/{code}/history")
async def get_sector_history(code: str, days: int = Query(120, ge=30, le=250)):
    try:
        result = await asyncio.to_thread(sector_history, code, days)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"板块走势获取失败: {exc}") from exc
    return {"status": "ok", "result": result}


@router.get("/sectors/{code}/constituents")
async def get_sector_constituents(
    code: str,
    limit: int = Query(80, ge=1, le=200),
    mode: FormulaMode = Query("balanced"),
):
    try:
        result = await asyncio.to_thread(sector_constituents, code, limit)
        enriched = await asyncio.to_thread(enrich_stock_history, result["items"], limit)
        ranked = [_rank_live_item(item, mode) for item in enriched]
        ranked.sort(key=lambda item: item["formula_score"], reverse=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"板块成分股评分失败: {exc}") from exc

    return {
        "status": "ok",
        "result": {
            **result,
            "mode": mode,
            "formula": FORMULA_DESCRIPTION,
            "items": ranked,
            "history_enriched_count": sum(
                1
                for item in ranked
                if all(isinstance(item.get(key), (int, float)) for key in ("change_5d", "change_20d", "change_60d"))
            ),
        },
    }
