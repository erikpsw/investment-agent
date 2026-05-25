"""Unified AI stock picker routes."""
from __future__ import annotations

import asyncio
import traceback
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from investment.data.stock_picker import get_stock_picker_service


router = APIRouter()


class StockPickerRequest(BaseModel):
    markets: List[str] = Field(default_factory=lambda: ["CN", "US"])
    limit: int = Field(default=8, ge=3, le=20)
    notes: str = ""


@router.post("/stock-picker/analyze")
async def analyze_stock_picker(req: StockPickerRequest):
    service = get_stock_picker_service()
    try:
        result = await asyncio.to_thread(service.analyze, req.markets, req.limit, req.notes)
        return {"status": "ok", "result": result}
    except Exception as exc:
        detail = f"{exc}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=detail)


@router.get("/stock-picker/results")
async def stock_picker_results(limit: int = Query(default=20, ge=1, le=100)):
    service = get_stock_picker_service()
    return {"status": "ok", "result": service.read_results(limit=limit)}


@router.delete("/stock-picker/results")
async def clear_stock_picker_results():
    service = get_stock_picker_service()
    return {"status": "ok", "result": service.clear_results()}
