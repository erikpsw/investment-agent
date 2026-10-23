"""Observed scores, comparable changes and bounded user-scoped detection."""
import asyncio
from datetime import datetime, timezone, timedelta
import hashlib
import json
from zoneinfo import ZoneInfo

from investment.data.formula_scoring import WEIGHTS, number
from investment.data.security_scoring import security_identity, score_security


def instant(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def comparable(a, b):
    return bool(b) and all(a.get(k) is not None and a.get(k) == b.get(k) for k in
        ("market", "ticker", "mode", "formula_version", "config_fingerprint"))


def quality_status(snapshot, now=None):
    from investment.data.market_cache import is_market_open
    now = now or datetime.now(timezone.utc)
    stamp = instant(snapshot.get("quote_as_of"))
    if stamp is None or stamp > now:
        return "unverified_time"
    age = (now - stamp).total_seconds()
    market = snapshot.get("market", "CN")
    if age > 4 * 86400 or (is_market_open(market, now) and age > 900):
        return "stale_quote"
    if not is_market_open(market, now):
        local = now.astimezone(ZoneInfo({"CN":"Asia/Shanghai","HK":"Asia/Hong_Kong","US":"America/New_York"}[market]))
        close = local.replace(hour=15 if market=="CN" else 16, minute=0, second=0, microsecond=0)
        if local.weekday()<5 and market in ("CN","HK") and 11 <= local.hour < 13 and (local.hour,local.minute)>=(11,30) and market=="CN":
            close = local.replace(hour=11,minute=30,second=0,microsecond=0)
        elif local.weekday()<5 and market=="HK" and local.hour==12:
            close = local.replace(hour=12,minute=0,second=0,microsecond=0)
        elif local<close:
            close-=timedelta(days=1)
        while close.weekday()>=5:
            close-=timedelta(days=1)
        # Without an exchange holiday calendar, fail conservatively rather than treating an old weekday quote as fresh.
        if stamp < close-timedelta(minutes=15):
            return "stale_quote"
    if (number(snapshot.get("data_coverage")) or 0) < .65:
        return "insufficient_data"
    return "ok"


def compare_score_history(current, records, entry=None):
    stamp = instant(current.get("quote_as_of"))
    previous = sorted([r for r in records if comparable(current, r) and
        instant(r.get("quote_as_of")) and stamp and instant(r["quote_as_of"]) < stamp],
        key=lambda r: instant(r["quote_as_of"]))
    last = previous[-1] if previous else None
    score = number(current.get("formula_score"))
    def delta(old):
        old_score = number((old or {}).get("formula_score"))
        return round(score - old_score, 4) if comparable(current, old) and score is not None and old_score is not None else None
    reasons = []
    if last:
        for name in set(current.get("contributions", {})) | set(last.get("contributions", {})):
            new, old = number(current.get("contributions", {}).get(name)), number(last.get("contributions", {}).get(name))
            if new is not None and old is not None and new != old:
                reasons.append({"factor": name, "delta": round(new - old, 4)})
    zone = ZoneInfo({"CN": "Asia/Shanghai", "US": "America/New_York", "HK": "Asia/Hong_Kong"}[current["market"]])
    daily = {}
    for row in previous + [current]:
        time = instant(row.get("quote_as_of"))
        if time:
            daily[time.astimezone(zone).date().isoformat()] = row
    rows = [daily[k] for k in sorted(daily)]
    def trend(n):
        enough = len(rows) >= n + 1
        return {"status": "ok" if enough else "insufficient_history", "observed_sessions": len(rows),
                "delta": delta(rows[-n-1]) if enough else None,
                "from_quote_as_of": rows[-n-1]["quote_as_of"] if enough else None, "to_quote_as_of": current.get("quote_as_of")}
    return {"previous_delta": delta(last), "entry_delta": delta(entry),
            "comparable": last is not None, "entry_status": "comparable" if comparable(current, entry) else "not_recorded" if not entry else "incomparable",
            "quality_changed": bool(last and (last.get("data_coverage") != current.get("data_coverage") or
                last.get("missing_fields", []) != current.get("missing_fields", []))),
            "reasons": sorted(reasons, key=lambda r: (-abs(r["delta"]), r["factor"])),
            "trend_5d": trend(5), "trend_20d": trend(20)}


class ScoreTrackingService:
    def __init__(self, store, scorer=score_security):
        self.store, self.scorer = store, scorer

    async def detect(self, user_id, securities, mode, request_id):
        if mode not in WEIGHTS or not 1 <= len(securities) <= 50:
            raise ValueError("无效模式或检测数量，最多50只")
        identities = list(dict.fromkeys(security_identity(s["market"], s["ticker"]) for s in securities))
        semaphore = asyncio.Semaphore(4)
        deadline = asyncio.get_running_loop().time() + 40
        async def detect_one(market, ticker):
            async with semaphore:
                try:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise TimeoutError("本轮检测时间已用尽，请稍后重试")
                    item = await asyncio.wait_for(self.scorer(market, ticker, mode), timeout=remaining)
                    stamp = instant(item.get("quote_as_of"))
                    if not stamp or stamp > datetime.now(timezone.utc):
                        raise ValueError("报价时间缺失、未核验或位于未来")
                    if number(item.get("formula_score")) is None or (number(item.get("data_coverage")) or 0) < .65:
                        raise ValueError("评分输入不足，暂不记录趋势")
                    fingerprint = hashlib.sha256(json.dumps({"version": item.get("formula_version"), "mode": mode,
                        "weights": item.get("weights", WEIGHTS[mode])}, sort_keys=True).encode()).hexdigest()
                    snapshot = {**item, "market": market, "ticker": ticker, "mode": mode,
                                "config_fingerprint": fingerprint, "quote_as_of": stamp.isoformat(),
                                "observed_at": datetime.now(timezone.utc).isoformat(), "request_id": str(request_id)}
                    snapshot["quality_status"] = quality_status(snapshot)
                    snapshot["price_basis"] = "raw"
                    if snapshot["quality_status"] != "ok":
                        return {"market": market, "ticker": ticker, "status": "unavailable", "snapshot": snapshot,
                                "message": "报价已过期，保留展示但不新增评分趋势或仓位建议"}
                    history = await asyncio.to_thread(self.store.history, user_id, market, ticker, None, 200, 90)
                    saved = await asyncio.to_thread(self.store.append_snapshot, user_id, snapshot)
                    latest = saved["snapshot"]
                    return {"market": market, "ticker": ticker, "status": "ok", **saved,
                            "change": compare_score_history(latest, history["items"])}
                except Exception as exc:
                    from fastapi import HTTPException
                    message = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
                    return {"market": market, "ticker": ticker, "status": "unavailable", "message": message[:180] or "评分检测暂不可用"}
        return {"items": await asyncio.gather(*(detect_one(*identity) for identity in identities)), "mode": mode}
