"""Portfolio API routes."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Literal, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime

from investment.api.auth import AuthenticatedUser, get_auth0_user, require_scope
from investment.data.portfolio import get_portfolio_service
from investment.data.portfolio_store import PortfolioStorageError, PortfolioRevisionConflict


router = APIRouter()
get_portfolio_reader = require_scope("portfolio:read")
get_portfolio_writer = require_scope("portfolio:write")


async def _run_portfolio_call(call: Callable[..., Any], *args: Any) -> Any:
    try:
        return await asyncio.to_thread(call, *args)
    except PortfolioRevisionConflict as exc:
        raise HTTPException(409, "持仓已启用管理或已更新，请刷新后使用当前修订号") from exc
    except PortfolioStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Portfolio storage is unavailable",
        ) from exc


class PortfolioPosition(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
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
    request_id: Optional[UUID] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)


class PortfolioTransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    action: Literal["buy", "sell", "set_cash", "adjust_cash"]
    instrument_id: str = ""
    name: str = ""
    market: str = ""
    quantity: Optional[float] = Field(default=None, gt=0)
    price: Optional[float] = Field(default=None, gt=0)
    currency: Optional[Literal["CNY", "HKD", "USD"]] = None
    amount: Optional[float] = None
    request_id: Optional[UUID] = None
    expected_revision: Optional[int] = Field(default=None, ge=0)
    executed_at: Optional[AwareDatetime] = None
    score_snapshot_id: Optional[UUID] = None
    fee: float = Field(default=0, ge=0)


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
    if request.expected_revision is not None:
        from investment.api.routes.score_tracking import store_dependency, call
        try:
            normalized = get_portfolio_service()._normalize_positions(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        state = await call(store_dependency().apply_event, current_user.sub, request.request_id or uuid4(),
            request.expected_revision, {"action": "replace_positions", "positions": normalized})
        result = await _run_portfolio_call(get_portfolio_service().get_positions, current_user.sub, False, False)
        result["revision"] = state["revision"]
        return {"status": "ok", "result": result}
    result = await _run_portfolio_call(
        get_portfolio_service().save_positions,
        current_user.sub,
        payload,
    )
    return {"status": "ok", "result": result}


@router.post("/portfolio/transactions")
async def apply_portfolio_transaction(
    request: PortfolioTransactionRequest,
    current_user: AuthenticatedUser = Depends(get_portfolio_writer),
):
    if request.request_id is not None:
        if request.expected_revision is None:
            raise HTTPException(422, "记账需要当前持仓修订号")
        from investment.api.routes.score_tracking import store_dependency, call
        from investment.data.security_scoring import security_identity
        event = request.model_dump(mode="json", exclude_none=True, exclude={"request_id", "expected_revision"})
        if request.action in ("buy", "sell"):
            try:
                event["market"], event["instrument_id"] = security_identity(request.market, request.instrument_id)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        return {"status": "ok", "result": await call(store_dependency().apply_event, current_user.sub,
            request.request_id, request.expected_revision, event)}
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
