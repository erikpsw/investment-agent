"""Portfolio API routes."""
from __future__ import annotations

import asyncio
from typing import Any, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from investment.data.portfolio import get_portfolio_service


router = APIRouter()


class PortfolioPosition(BaseModel):
    ticker: str
    name: str = ""
    market: str = ""
    quantity: float = Field(default=0, ge=0)
    avg_cost: float = Field(default=0, ge=0)
    notes: str = ""


class PortfolioPositionsRequest(BaseModel):
    positions: List[PortfolioPosition]


@router.get("/portfolio/positions")
async def get_positions():
    return {"status": "ok", "result": get_portfolio_service().get_positions()}


@router.put("/portfolio/positions")
async def save_positions(request: PortfolioPositionsRequest):
    payload: List[dict[str, Any]] = [item.dict() for item in request.positions]
    result = await asyncio.to_thread(get_portfolio_service().save_positions, payload)
    return {"status": "ok", "result": result}


@router.post("/portfolio/analyze")
async def analyze_portfolio():
    result = await asyncio.to_thread(get_portfolio_service().analyze)
    return {"status": "ok", "result": result}
