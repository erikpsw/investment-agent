"""Portfolio API routes."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from investment.api.auth import AuthenticatedUser, get_auth0_user, require_scope
from investment.data.portfolio import get_portfolio_service
from investment.data.portfolio_store import PortfolioStorageError


router = APIRouter()
get_portfolio_reader = require_scope("portfolio:read")


async def _run_portfolio_call(call: Callable[..., Any], *args: Any) -> Any:
    try:
        return await asyncio.to_thread(call, *args)
    except PortfolioStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Portfolio storage is unavailable",
        ) from exc


class PortfolioPosition(BaseModel):
    ticker: str
    name: str = ""
    market: str = ""
    currency: str = ""
    quantity: float = Field(default=0, ge=0)
    avg_cost: float = Field(default=0, ge=0)
    notes: str = ""


class PortfolioPositionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positions: List[PortfolioPosition]


@router.get("/portfolio/positions")
async def get_positions(current_user: AuthenticatedUser = Depends(get_portfolio_reader)):
    result = await _run_portfolio_call(get_portfolio_service().get_positions, current_user.sub)
    return {"status": "ok", "result": result}


@router.put("/portfolio/positions")
async def save_positions(
    request: PortfolioPositionsRequest,
    current_user: AuthenticatedUser = Depends(get_auth0_user),
):
    payload: List[dict[str, Any]] = [item.model_dump() for item in request.positions]
    result = await _run_portfolio_call(
        get_portfolio_service().save_positions,
        current_user.sub,
        payload,
    )
    return {"status": "ok", "result": result}


@router.post("/portfolio/analyze")
async def analyze_portfolio(current_user: AuthenticatedUser = Depends(get_portfolio_reader)):
    result = await _run_portfolio_call(get_portfolio_service().analyze, current_user.sub)
    return {"status": "ok", "result": result}
