"""Lightweight full-market A-share scanner for the Vercel deployment."""
from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import requests


EASTMONEY_URLS = [
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
]
PAGE_SIZE = 100
FIELDS = "f2,f3,f5,f6,f8,f9,f10,f12,f14,f20,f21,f23,f24,f25"
MARKET_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
CACHE_SECONDS = 600

_cache_lock = Lock()
_cache: dict[str, Any] = {"expires_at": 0.0, "rows": [], "generated_at": None}
_history_cache: dict[str, tuple[float, dict[str, float | None]]] = {}
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "storage" / "market" / "latest.json"


def scan_cn_market() -> dict[str, Any]:
    snapshot = _read_snapshot()
    if snapshot:
        return snapshot

    now = time.time()
    with _cache_lock:
        if _cache["rows"] and now < _cache["expires_at"]:
            return {
                "rows": list(_cache["rows"]),
                "generated_at": _cache["generated_at"],
                "cached": True,
            }

    first_data = _fetch_page(1)
    total = int(first_data.get("total") or 0)
    rows = list(first_data.get("diff") or [])
    page_count = max(1, math.ceil(total / PAGE_SIZE))

    if page_count > 1:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(_fetch_page, page): page for page in range(2, page_count + 1)}
            for future in as_completed(futures):
                rows.extend(future.result().get("diff") or [])

    normalized = [_normalize(row) for row in rows]
    filtered = [row for row in normalized if row is not None]
    generated_at = datetime.now().astimezone().isoformat()
    if len(filtered) < 4500:
        raise RuntimeError(f"全市场行情返回不完整，仅获取 {len(filtered)} 只")

    with _cache_lock:
        _cache.update(
            {
                "expires_at": now + CACHE_SECONDS,
                "rows": filtered,
                "generated_at": generated_at,
            }
        )
    return {"rows": filtered, "generated_at": generated_at, "cached": False, "source": "东方财富实时全市场"}


def _read_snapshot() -> dict[str, Any] | None:
    if not SNAPSHOT_PATH.exists():
        return None
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) < 4500:
        return None
    return {
        "rows": rows,
        "generated_at": payload.get("generated_at"),
        "cached": True,
        "source": "GitHub Actions 交易日全市场快照",
    }


def enrich_stock_history(rows: list[dict[str, Any]], limit: int = 120) -> list[dict[str, Any]]:
    selected = sorted(rows, key=_snapshot_priority, reverse=True)[:limit]
    by_ticker = {str(row["ticker"]): dict(row) for row in selected}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_stock_returns, ticker): ticker for ticker in by_ticker}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                by_ticker[ticker].update(future.result())
            except Exception:
                continue
    return list(by_ticker.values())


def _fetch_page(page: int) -> dict[str, Any]:
    params = {
        "pn": page,
        "pz": PAGE_SIZE,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f12",
        "fs": MARKET_FILTER,
        "fields": FIELDS,
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://quote.eastmoney.com/",
    }
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = requests.get(EASTMONEY_URLS[attempt % len(EASTMONEY_URLS)], params=params, headers=headers, timeout=12)
            response.raise_for_status()
            data = response.json().get("data")
            if isinstance(data, dict):
                return data
        except Exception as exc:
            last_error = exc
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"行情第 {page} 页获取失败: {last_error}")


def _stock_returns(ticker: str) -> dict[str, float | None]:
    now = time.time()
    cached = _history_cache.get(ticker)
    if cached and now < cached[0]:
        return dict(cached[1])

    code = ticker[2:]
    secid = f"{'1' if ticker.startswith('sh') else '0'}.{code}"
    end = datetime.now()
    begin = end - timedelta(days=150)
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": begin.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "lmt": "120",
    }
    data: dict[str, Any] = {}
    last_error: Exception | None = None
    for attempt in range(1):
        try:
            response = requests.get(
                "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                params=params,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
                timeout=5,
            )
            response.raise_for_status()
            data = response.json().get("data") or {}
            if data.get("klines"):
                break
        except Exception as exc:
            last_error = exc
            time.sleep(0.2 * (attempt + 1))
    if not data.get("klines"):
        raise RuntimeError(f"{ticker} 历史行情获取失败: {last_error}")
    closes = [_number(str(item).split(",")[2]) for item in data.get("klines") or []]
    valid = [value for value in closes if value is not None and value > 0]
    result = {
        "change_5d": _period_return(valid, 5),
        "change_20d": _period_return(valid, 20),
        "change_60d": _period_return(valid, 60),
    }
    _history_cache[ticker] = (now + CACHE_SECONDS, result)
    return result


def _period_return(closes: list[float], days: int) -> float | None:
    if len(closes) <= days or closes[-days - 1] <= 0:
        return None
    return round((closes[-1] / closes[-days - 1] - 1) * 100, 2)


def _snapshot_priority(row: dict[str, Any]) -> float:
    change = _number(row.get("today_change_percent")) or 0
    trend = _number(row.get("change_60d")) or 0
    volume_ratio = _number(row.get("volume_ratio")) or 0
    turnover = _number(row.get("turnover_rate")) or 0
    return (
        min(max(change, -5), 8) * 2
        + min(max(trend, -20), 50) * 0.5
        + min(volume_ratio, 5) * 4
        + min(turnover, 15)
    )


def _normalize(row: dict[str, Any]) -> dict[str, Any] | None:
    code = str(row.get("f12") or "")
    name = str(row.get("f14") or "").strip()
    if not code or not name or "ST" in name.upper() or "退" in name:
        return None
    if not code.startswith(("600", "601", "603", "605", "688", "000", "001", "002", "003", "300", "301")):
        return None

    price = _number(row.get("f2"))
    change = _number(row.get("f3"))
    amount = _number(row.get("f6"))
    market_cap = _number(row.get("f20"))
    if price is None or price <= 0 or change is None or amount is None or amount <= 0:
        return None
    if market_cap is None or market_cap <= 0:
        return None

    prefix = "sh" if code.startswith("6") else "sz"
    return {
        "ticker": f"{prefix}{code}",
        "name": name,
        "market": "CN",
        "price": price,
        "today_change_percent": change,
        "turnover_rate": _number(row.get("f8")),
        "pe_ratio": _number(row.get("f9")),
        "volume_ratio": _number(row.get("f10")),
        "market_cap": market_cap,
        "float_market_cap": _number(row.get("f21")),
        "pb_ratio": _number(row.get("f23")),
        "change_60d": _number(row.get("f24")),
        "change_ytd": _number(row.get("f25")),
    }


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    try:
        parsed = float(str(value))
        return parsed if math.isfinite(parsed) else None
    except Exception:
        return None
