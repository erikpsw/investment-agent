"""Portfolio API routes."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
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
    avg_cost: float = 0
    notes: str = ""


class PortfolioPositionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    positions: List[PortfolioPosition]


class PortfolioTransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["buy", "sell", "set_cash", "adjust_cash"]
    instrument_id: str = ""
    name: str = ""
    market: str = ""
    quantity: Optional[float] = Field(default=None, gt=0)
    price: Optional[float] = Field(default=None, gt=0)
    currency: Optional[Literal["CNY", "HKD", "USD"]] = None
    amount: Optional[float] = None


@router.get("/portfolio/positions")
async def get_positions(
    include_history: bool = Query(default=False),
    include_research: bool = Query(default=True),
    current_user: AuthenticatedUser = Depends(get_portfolio_reader),
):
    result = await _run_portfolio_call(
        get_portfolio_service().get_positions,
        current_user.sub,
        include_history,
        include_research,
    )
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


@router.post("/portfolio/transactions")
async def apply_portfolio_transaction(
    request: PortfolioTransactionRequest,
    current_user: AuthenticatedUser = Depends(get_portfolio_reader),
):
    try:
        result = await _run_portfolio_call(
            get_portfolio_service().apply_transaction,
            current_user.sub,
            request.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "result": result}


@router.post("/portfolio/analyze")
async def analyze_portfolio(current_user: AuthenticatedUser = Depends(get_portfolio_reader)):
    result = await _run_portfolio_call(get_portfolio_service().analyze, current_user.sub)
    return {"status": "ok", "result": result}
