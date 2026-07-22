"""Authenticated grouped watchlist API routes."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from investment.api.auth import AuthenticatedUser, require_scope
from investment.data.watchlist_store import WatchlistStorageError
from investment.data.watchlists import (
    WatchlistGroupNotFound,
    get_watchlist_service,
)


router = APIRouter()
get_watchlist_reader = require_scope("portfolio:read")
get_watchlist_writer = require_scope("portfolio:write")


class WatchlistItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1, max_length=40)
    name: str = Field(default="", max_length=160)
    market: str = Field(default="", max_length=12)
    notes: str = Field(default="", max_length=1000)


class WatchlistGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    items: List[WatchlistItemRequest] = Field(default_factory=list, max_length=500)


class WatchlistsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: List[WatchlistGroupRequest] = Field(default_factory=list, max_length=100)


async def _run_watchlist_call(call: Callable[..., Any], *args: Any) -> Any:
    try:
        return await asyncio.to_thread(call, *args)
    except WatchlistGroupNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Watchlist group was not found",
        ) from exc
    except WatchlistStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Watchlist storage is unavailable",
        ) from exc


@router.get("/watchlists")
async def get_watchlists(
    group_id: Optional[str] = Query(default=None, min_length=1, max_length=100),
    include_history: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_watchlist_reader),
):
    result = await _run_watchlist_call(
        get_watchlist_service().get_watchlists,
        current_user.sub,
        group_id,
        include_history,
    )
    return {"status": "ok", "result": result}


@router.put("/watchlists")
async def save_watchlists(
    request: WatchlistsRequest,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    groups = [group.model_dump() for group in request.groups]
    result = await _run_watchlist_call(
        get_watchlist_service().save_watchlists,
        current_user.sub,
        groups,
    )
    return {"status": "ok", "result": result}
