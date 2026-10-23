"""User-private durable score records and portfolio management RPCs."""
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from threading import RLock
from uuid import uuid4
from zoneinfo import ZoneInfo

from investment.data.score_tracking import instant


class TrackingStorageError(RuntimeError):
    pass


class TrackingConflict(ValueError):
    pass


def _owner(owner):
    if not isinstance(owner, str) or not owner.strip():
        raise ValueError("用户身份缺失")
    return owner


def _inputs(row):
    return {k: v for k, v in row.items() if k not in ("id", "observed_at", "request_id")}


class InMemoryScoreTrackingStore:
    """Explicit test fixture, never used as a production fallback."""
    def __init__(self):
        self.rows = {}
        self.lock = RLock()

    def append_snapshot(self, owner, snapshot):
        _owner(owner)
        stamp = instant(snapshot.get("quote_as_of"))
        if stamp is None:
            raise ValueError("报价时间无效")
        with self.lock:
            rows = self.rows.setdefault(owner, [])
            peers = [r for r in rows if all(r.get(k) == snapshot.get(k) for k in
                ("market", "ticker", "mode", "config_fingerprint"))]
            latest = max(peers, key=lambda r: instant(r["quote_as_of"]), default=None)
            if latest and instant(latest["quote_as_of"]) >= stamp:
                if instant(latest["quote_as_of"]) == stamp and _inputs(latest) != _inputs(snapshot):
                    raise TrackingConflict("同一报价时点的评分输入不一致，请重新检测")
                return {"saved": True, "inserted": False, "snapshot": deepcopy(latest)}
            row = {**deepcopy(snapshot), "id": str(uuid4())}
            rows.append(row)
            return {"saved": True, "inserted": True, "snapshot": deepcopy(row)}

    def history(self, owner, market, ticker, cursor=None, limit=200, trading_days=30):
        _owner(owner)
        if not 1 <= limit <= 200 or trading_days not in (30, 90):
            raise ValueError("无效历史范围")
        zone = ZoneInfo({"CN": "Asia/Shanghai", "US": "America/New_York", "HK": "Asia/Hong_Kong"}[market])
        with self.lock:
            rows = sorted([r for r in self.rows.get(owner, []) if r["market"] == market and r["ticker"] == ticker],
                          key=lambda r: (instant(r["quote_as_of"]), r["id"]), reverse=True)
            days = sorted({instant(r["quote_as_of"]).astimezone(zone).date() for r in rows}, reverse=True)[:trading_days]
            rows = [r for r in rows if instant(r["quote_as_of"]).astimezone(zone).date() in days]
            if cursor:
                index = next((i for i, r in enumerate(rows) if r["id"] == cursor), None)
                if index is None:
                    raise ValueError("历史分页游标无效")
                rows = rows[index + 1:]
            selected = rows[:limit]
            return {"items": deepcopy(selected), "next_cursor": selected[-1]["id"] if len(rows) > limit else None}


class SupabaseScoreTrackingStore:
    def __init__(self, client):
        self.client = client

    def rpc(self, name, args):
        try:
            response = self.client.rpc(name, args).execute()
            return response.data
        except Exception as exc:
            code = str(getattr(exc, "code", ""))
            if code in ("PT409", "40001", "23505"):
                raise TrackingConflict("记录已变化或重复，请刷新后重试") from exc
            if code == "22023":
                raise ValueError("提交内容、评分关联或保护计划无效") from exc
            raise TrackingStorageError("评分管理存储暂不可用，本次操作未确认成功") from exc

    def append_snapshot(self, owner, snapshot):
        return self.rpc("append_security_score", {"p_owner": _owner(owner), "p_snapshot": snapshot})

    def history(self, owner, market, ticker, cursor=None, limit=200, trading_days=30):
        return self.rpc("security_score_history", {"p_owner": _owner(owner), "p_market": market,
            "p_ticker": ticker, "p_cursor": cursor, "p_limit": limit, "p_days": trading_days})

    def get_state(self, owner):
        return self.rpc("portfolio_management_state", {"p_owner": _owner(owner)})

    def latest(self, owner, mode):
        return self.rpc("portfolio_latest_scores", {"p_owner": _owner(owner), "p_mode": mode})

    def apply_event(self, owner, request_id, expected_revision, event):
        return self.rpc("apply_portfolio_event", {"p_owner": _owner(owner), "p_request_id": str(request_id),
            "p_expected_revision": expected_revision, "p_event": event})

    def confirm_protection(self, owner, market, ticker, episode_id, expected_revision, plan):
        return self.apply_event(owner, str(uuid4()), expected_revision, {"action": "protection", "market": market,
            "instrument_id": ticker, "episode_id": episode_id, "plan": plan})

    def save_risk_settings(self, owner, settings):
        return self.rpc("save_portfolio_risk_settings", {"p_owner": _owner(owner), "p_settings": settings})


@lru_cache(maxsize=1)
def get_score_tracking_store():
    from investment.data.portfolio_store import get_portfolio_store
    portfolio = get_portfolio_store()
    client = getattr(portfolio, "_client", None)
    if client is None:
        raise TrackingStorageError("云端管理存储未配置")
    return SupabaseScoreTrackingStore(client)
