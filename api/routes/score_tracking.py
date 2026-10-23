"""Authenticated observed-score history and long-position management."""
import asyncio
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from investment.api.auth import AuthenticatedUser, require_scope
from investment.data.score_tracking import ScoreTrackingService, compare_score_history, quality_status, instant
from investment.data.score_tracking_store import get_score_tracking_store, TrackingStorageError, TrackingConflict
from investment.data.security_scoring import security_identity
from investment.data.position_management import risk_overview, protection_candidate

router = APIRouter()
reader = require_scope("portfolio:read")
writer = require_scope("portfolio:write")


def store_dependency():
    try:
        return get_score_tracking_store()
    except Exception as exc:
        raise HTTPException(503, "评分管理存储尚未就绪，请核对数据库迁移与配置") from exc


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Security(StrictModel):
    market: Literal["CN", "HK", "US"]
    ticker: str = Field(min_length=1, max_length=20)


class DetectionRequest(StrictModel):
    securities: list[Security] = Field(min_length=1, max_length=50)
    mode: Literal["balanced", "conservative", "aggressive"] = "balanced"
    request_id: UUID


class RiskSettings(StrictModel):
    mode: Literal["balanced", "conservative", "aggressive"] = "balanced"
    risk_budget_percent: float = Field(default=1, ge=.1, le=2)
    position_cap_percent: float = Field(default=20, ge=1, le=30)
    total_risk_percent: float | None = Field(default=None, ge=.1, le=10)
    one_way_cost: float = Field(default=.0015, ge=0, le=.05)


class Protection(StrictModel):
    snapshot_id: UUID
    config_fingerprint: str = Field(min_length=1, max_length=128)
    quote_as_of: str = Field(min_length=1, max_length=60)
    currency: Literal["CNY", "USD", "HKD"]
    price_basis: Literal["raw"] = "raw"
    reference_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    take_profit_1: float | None = Field(default=None, gt=0)
    take_profit_2: float | None = Field(default=None, gt=0)
    lot_size: int | None = Field(default=None, ge=1)


class ProtectionRequest(StrictModel):
    episode_id: UUID
    expected_revision: int = Field(ge=0)
    plan: Protection


class TrackingRequest(StrictModel):
    request_id: UUID
    expected_revision: int = Field(ge=0)


def allowed_securities(owner):
    from investment.data.watchlists import get_watchlist_service
    from investment.data.portfolio_store import get_portfolio_store
    groups = get_watchlist_service().store.load(owner).groups
    positions = get_portfolio_store().load(owner).positions
    def members(groups):
        return [item for group in groups for item in group.get("items", [])] + [item for group in groups for item in members(group.get("children", []))]
    rows = positions + members(groups)
    identities = set()
    for row in rows:
        try:
            identities.add(security_identity(row.get("market", ""), row.get("ticker", "")))
        except ValueError:
            continue
    return identities


async def call(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except TrackingConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except TrackingStorageError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/watchlists/detection")
async def detect(request: DetectionRequest, user: AuthenticatedUser = Depends(writer), store=Depends(store_dependency)):
    try:
        identities = {security_identity(s.market, s.ticker) for s in request.securities}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        allowed = await asyncio.to_thread(allowed_securities, user.sub)
    except Exception as exc:
        raise HTTPException(503, "无法核验自选与持仓成员，本次未执行检测") from exc
    if not identities <= allowed:
        raise HTTPException(403, "只能检测当前用户的自选或持仓证券")
    result = await ScoreTrackingService(store).detect(user.sub, [s.model_dump() for s in request.securities], request.mode, request.request_id)
    return {"status": "ok", "result": result}


@router.get("/securities/{market}/{ticker}/score-history")
async def history(market: Literal["CN", "HK", "US"], ticker: str, cursor: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=200), trading_days: int = Query(default=30, ge=30, le=90),
    user: AuthenticatedUser = Depends(reader), store=Depends(store_dependency)):
    try:
        market, ticker = security_identity(market, ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if trading_days not in (30, 90):
        raise HTTPException(422, "历史范围仅支持30或90个观察日")
    return {"status": "ok", "result": await call(store.history, user.sub, market, ticker, str(cursor) if cursor else None, limit, trading_days)}


async def verified_fx(currencies):
    """Never reuse portfolio valuation's approximate fallback exchange rates."""
    from investment.data.stock_fetcher import StockFetcher
    fetcher = StockFetcher()
    async def fetch(currency):
        try:
            quote = await asyncio.wait_for(asyncio.to_thread(fetcher.yfinance.get_quote,
                {"USD": "CNY=X", "HKD": "HKDCNY=X"}[currency]), timeout=10)
            stamp = instant(quote.get("timestamp"))
            price = quote.get("price")
            if stamp and 0 <= (datetime.now(timezone.utc) - stamp).total_seconds() <= 4 * 86400 and isinstance(price, (int, float)) and 0 < price < 100:
                return currency, price
        except Exception:
            pass
        return currency, None
    rates = await asyncio.gather(*(fetch(c) for c in currencies if c in ("USD", "HKD")))
    return {"CNY": 1, **{c: v for c, v in rates if v is not None}}


@router.get("/portfolio/risk-overview")
async def overview(user: AuthenticatedUser = Depends(reader), store=Depends(store_dependency)):
    state = await call(store.get_state, user.sub)
    settings = state.get("settings", {})
    latest = await call(store.latest, user.sub, settings.get("mode", "balanced"))
    positions, cash = [], {}
    for row in state["positions"]:
        if row.get("market") == "CASH" or row.get("ticker", "").upper().startswith("CASH_"):
            cash[row.get("currency") or row["ticker"].removeprefix("CASH_")] = row.get("quantity", 0)
        else:
            try:
                market, ticker = security_identity(row.get("market", ""), row.get("ticker", ""))
                positions.append({**row, "market": market, "ticker": ticker})
            except ValueError:
                raise HTTPException(422, "持仓包含无法核验的市场或代码，请先修正")
    for key, snapshot in latest.items():
        snapshot["quality_status"] = quality_status(snapshot)
        entry = state.get("management", {}).get(key, {}).get("entry_snapshot")
        records = await call(store.history, user.sub, snapshot["market"], snapshot["ticker"], None, 200, 30)
        snapshot["change"] = compare_score_history(snapshot, records["items"], entry)
    fx = await verified_fx(set(cash) | {p.get("currency") for p in positions})
    result = risk_overview(positions, cash, settings, fx, latest, state.get("management", {}))
    for row in result["items"]:
        current = row["detection"]
        fresh = current.get("risk_plan", {})
        if current.get("quality_status") != "ok":
            fresh = {"status": "insufficient_data"}
        if fresh.get("status") == "ok":
            fresh = {**fresh, "price_basis": "raw", "snapshot_id": current["id"],
                "config_fingerprint": current["config_fingerprint"], "quote_as_of": current["quote_as_of"]}
        managed = row["management"]
        row["protection_candidate"] = protection_candidate(managed.get("protection"), fresh, managed.get("episode_id"),
            {"currency": row["currency"], "price_basis": "raw", "reference_price": current.get("price")})
    return {"status": "ok", "result": {**result, "revision": state["revision"], "fx_verified": fx}}


@router.put("/portfolio/risk-settings")
async def settings(request: RiskSettings, user: AuthenticatedUser = Depends(writer), store=Depends(store_dependency)):
    return {"status": "ok", "result": await call(store.save_risk_settings, user.sub, request.model_dump(exclude_none=True))}


@router.put("/portfolio/positions/{market}/{ticker}/protection")
async def confirm(market: Literal["CN", "HK", "US"], ticker: str, request: ProtectionRequest,
    user: AuthenticatedUser = Depends(writer), store=Depends(store_dependency)):
    try:
        market, ticker = security_identity(market, ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if request.plan.stop_loss >= request.plan.reference_price:
        raise HTTPException(422, "止损必须低于参考价")
    state = await call(store.get_state, user.sub)
    latest = await call(store.latest, user.sub, state.get("settings", {}).get("mode", "balanced"))
    snapshot = latest.get(market + ":" + ticker)
    if not snapshot or str(snapshot.get("id")) != str(request.plan.snapshot_id) or quality_status(snapshot) != "ok" or snapshot.get("config_fingerprint") != request.plan.config_fingerprint:
        raise HTTPException(409, "报价已过期或评分配置已变化，请重新检测后确认")
    return {"status": "ok", "result": await call(store.confirm_protection, user.sub, market, ticker,
        str(request.episode_id), request.expected_revision, request.plan.model_dump(mode="json", exclude_none=True))}


@router.post("/portfolio/positions/{market}/{ticker}/tracking")
async def adopt(market: Literal["CN", "HK", "US"], ticker: str, request: TrackingRequest,
    user: AuthenticatedUser = Depends(writer), store=Depends(store_dependency)):
    try:
        market, ticker = security_identity(market, ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"status": "ok", "result": await call(store.apply_event, user.sub, request.request_id, request.expected_revision,
        {"action": "adopt", "market": market, "instrument_id": ticker})}
