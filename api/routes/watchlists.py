"""Authenticated grouped watchlist API routes."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from investment.api.auth import AuthenticatedUser, require_scope
from investment.data.watchlist_store import WatchlistStorageError
from investment.data.watchlists import (
    WatchlistGroupNotFound,
    WatchlistItemNotFound,
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
    parent_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    items: List[WatchlistItemRequest] = Field(default_factory=list, max_length=500)


class WatchlistGroupCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    parent_id: Optional[str] = Field(default=None, min_length=1, max_length=100)


class WatchlistGroupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    parent_id: Optional[str] = Field(default=None, min_length=1, max_length=100)


class WatchlistItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, max_length=160)
    market: Optional[str] = Field(default=None, max_length=12)
    notes: Optional[str] = Field(default=None, max_length=1000)
    target_group_id: Optional[str] = Field(default=None, min_length=1, max_length=100)


class WatchlistsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: List[WatchlistGroupRequest] = Field(default_factory=list, max_length=100)


class WatchlistBatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["create", "get", "update", "delete"]
    resource: Literal["group", "item"]
    group_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    name: Optional[str] = Field(default=None, max_length=160)
    parent_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    ticker: Optional[str] = Field(default=None, min_length=1, max_length=40)
    tickers: Optional[List[str]] = Field(default=None, max_length=500)
    market: Optional[str] = Field(default=None, max_length=12)
    notes: Optional[str] = Field(default=None, max_length=1000)
    target_group_id: Optional[str] = Field(default=None, min_length=1, max_length=100)


class WatchlistBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operations: List[WatchlistBatchOperation] = Field(min_length=1, max_length=100)


async def _run_watchlist_call(call: Callable[..., Any], *args: Any) -> Any:
    try:
        return await asyncio.to_thread(call, *args)
    except WatchlistGroupNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="Watchlist group was not found",
        ) from exc
    except WatchlistItemNotFound as exc:
        raise HTTPException(status_code=404, detail="Watchlist item was not found") from exc
    except WatchlistStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Watchlist storage is unavailable",
        ) from exc


@router.get("/watchlists")
async def get_watchlists(
    group_id: Optional[str] = Query(default=None, min_length=1, max_length=100),
    include_history: bool = Query(default=False),
    include_research: bool = Query(default=True),
    quotes_only: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_watchlist_reader),
):
    result = await _run_watchlist_call(
        get_watchlist_service().get_watchlists,
        current_user.sub,
        group_id,
        include_history,
        include_research,
        quotes_only,
    )
    return {"status": "ok", "result": result}


@router.get("/watchlists/groups/{group_id}/items/{ticker}/research")
async def get_watchlist_item_research(
    group_id: str,
    ticker: str,
    current_user: AuthenticatedUser = Depends(get_watchlist_reader),
):
    result = await _run_watchlist_call(
        get_watchlist_service().get_item_research,
        current_user.sub,
        group_id,
        ticker,
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


@router.post("/watchlists/batch")
async def batch_watchlists(
    request: WatchlistBatchRequest,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    """Atomically apply up to 100 watchlist CRUD operations."""
    try:
        result = await _run_watchlist_call(
            get_watchlist_service().batch,
            current_user.sub,
            [operation.model_dump(exclude_unset=True) for operation in request.operations],
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "result": result}


@router.post("/watchlists/groups")
async def create_watchlist_group(
    request: WatchlistGroupCreateRequest,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    try:
        result = await _run_watchlist_call(get_watchlist_service().create_group, current_user.sub, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "result": result}


@router.patch("/watchlists/groups/{group_id}")
async def update_watchlist_group(
    group_id: str,
    request: WatchlistGroupUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    try:
        result = await _run_watchlist_call(get_watchlist_service().update_group, current_user.sub, group_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "result": result}


@router.delete("/watchlists/groups/{group_id}")
async def delete_watchlist_group(
    group_id: str,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    result = await _run_watchlist_call(get_watchlist_service().delete_group, current_user.sub, group_id)
    return {"status": "ok", "result": result}


@router.post("/watchlists/groups/{group_id}/items")
async def add_watchlist_item(
    group_id: str,
    request: WatchlistItemRequest,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    try:
        result = await _run_watchlist_call(get_watchlist_service().add_item, current_user.sub, group_id, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "result": result}


@router.patch("/watchlists/groups/{group_id}/items/{ticker}")
async def update_watchlist_item(
    group_id: str,
    ticker: str,
    request: WatchlistItemUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    try:
        result = await _run_watchlist_call(get_watchlist_service().update_item, current_user.sub, group_id, ticker, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "ok", "result": result}


@router.delete("/watchlists/groups/{group_id}/items/{ticker}")
async def delete_watchlist_item(
    group_id: str,
    ticker: str,
    current_user: AuthenticatedUser = Depends(get_watchlist_writer),
):
    result = await _run_watchlist_call(get_watchlist_service().delete_item, current_user.sub, group_id, ticker)
    return {"status": "ok", "result": result}
