"""Lightweight full-market A-share scanner for the Vercel deployment."""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from typing import Any

import requests


EASTMONEY_URL = "https://push2delay.eastmoney.com/api/qt/clist/get"
PAGE_SIZE = 100
FIELDS = "f2,f3,f5,f6,f8,f9,f10,f12,f14,f20,f21,f23,f24,f25"
MARKET_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
CACHE_SECONDS = 600

_cache_lock = Lock()
_cache: dict[str, Any] = {"expires_at": 0.0, "rows": [], "generated_at": None}


def scan_cn_market() -> dict[str, Any]:
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
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(_fetch_page, page): page for page in range(2, page_count + 1)}
            for future in as_completed(futures):
                try:
                    rows.extend(future.result().get("diff") or [])
                except Exception:
                    continue

    normalized = [_normalize(row) for row in rows]
    filtered = [row for row in normalized if row is not None]
    generated_at = datetime.now().astimezone().isoformat()
    if len(filtered) < 1000:
        raise RuntimeError(f"全市场行情返回不完整，仅获取 {len(filtered)} 只")

    with _cache_lock:
        _cache.update(
            {
                "expires_at": now + CACHE_SECONDS,
                "rows": filtered,
                "generated_at": generated_at,
            }
        )
    return {"rows": filtered, "generated_at": generated_at, "cached": False}


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
    for attempt in range(3):
        try:
            response = requests.get(EASTMONEY_URL, params=params, headers=headers, timeout=12)
            response.raise_for_status()
            data = response.json().get("data")
            if isinstance(data, dict):
                return data
        except Exception as exc:
            last_error = exc
            time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"行情第 {page} 页获取失败: {last_error}")


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
    return None
