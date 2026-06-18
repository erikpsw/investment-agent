"""Industry/sector snapshot and on-demand trend data."""
from __future__ import annotations

import math
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

import requests


LIST_URLS = [
    "https://17.push2.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
    "https://push2delay.eastmoney.com/api/qt/clist/get",
]
HISTORY_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
CACHE_SECONDS = 600
_lock = Lock()
_cache: dict[str, Any] = {"expires_at": 0.0, "rows": [], "generated_at": None}


def scan_sectors() -> dict[str, Any]:
    now = time.time()
    with _lock:
        if _cache["rows"] and now < _cache["expires_at"]:
            return {"rows": list(_cache["rows"]), "generated_at": _cache["generated_at"], "cached": True}

    first = _fetch_page(1)
    total = int(first.get("total") or 0)
    rows = list(first.get("diff") or [])
    page_count = math.ceil(total / 100)
    for page in range(2, page_count + 1):
        rows.extend(_fetch_page(page).get("diff") or [])

    normalized = [_normalize(row) for row in rows]
    result = [row for row in normalized if row is not None]
    if len(result) < 300:
        raise RuntimeError(f"板块行情返回不完整，仅获取 {len(result)} 个")
    generated_at = datetime.now().astimezone().isoformat()
    with _lock:
        _cache.update({"expires_at": now + CACHE_SECONDS, "rows": result, "generated_at": generated_at})
    return {"rows": result, "generated_at": generated_at, "cached": False}


def sector_history(code: str, days: int = 120) -> dict[str, Any]:
    end = datetime.now()
    begin = end - timedelta(days=max(days * 2, 180))
    params = {
        "secid": f"90.{code}",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "beg": begin.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "lmt": str(days + 20),
    }
    response = requests.get(HISTORY_URL, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
    response.raise_for_status()
    data = response.json().get("data") or {}
    bars = []
    for raw in (data.get("klines") or [])[-days:]:
        values = str(raw).split(",")
        if len(values) < 9:
            continue
        bars.append(
            {
                "date": values[0],
                "close": _number(values[2]),
                "change_percent": _number(values[8]),
                "turnover_rate": _number(values[10]) if len(values) > 10 else None,
            }
        )
    closes = [bar["close"] for bar in bars if isinstance(bar.get("close"), (int, float))]
    return {
        "code": code,
        "name": data.get("name"),
        "bars": bars,
        "change_5d": _return(closes, 5),
        "change_20d": _return(closes, 20),
        "change_60d": _return(closes, 60),
    }


def _fetch_page(page: int) -> dict[str, Any]:
    params = {
        "pn": page,
        "pz": 100,
        "po": 1,
        "np": 1,
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": "m:90 t:2 f:!50",
        "fields": "f2,f3,f8,f12,f14,f20,f24,f25,f104,f105,f128,f136,f140,f141",
    }
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            url = LIST_URLS[attempt % len(LIST_URLS)]
            response = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            response.raise_for_status()
            data = response.json().get("data")
            if isinstance(data, dict):
                return data
        except Exception as exc:
            last_error = exc
            time.sleep(0.3 * (attempt + 1))
    raise RuntimeError(f"板块第 {page} 页获取失败: {last_error}")


def _normalize(row: dict[str, Any]) -> dict[str, Any] | None:
    code = str(row.get("f12") or "")
    name = str(row.get("f14") or "")
    if not code or not name:
        return None
    up = int(_number(row.get("f104")) or 0)
    down = int(_number(row.get("f105")) or 0)
    change = _number(row.get("f3"))
    turnover = _number(row.get("f8"))
    breadth = round(up / max(up + down, 1) * 100, 1)
    score = round(
        max(0, min(100, 50 + (change or 0) * 5 + (breadth - 50) * 0.35 + min(turnover or 0, 10) * 1.5)),
        1,
    )
    leader_code = str(row.get("f140") or "")
    leader_prefix = "sh" if str(row.get("f141") or "") == "1" else "sz"
    return {
        "code": code,
        "name": name,
        "price": _number(row.get("f2")),
        "change_percent": change,
        "change_60d": _number(row.get("f24")),
        "change_ytd": _number(row.get("f25")),
        "turnover_rate": turnover,
        "market_cap": _number(row.get("f20")),
        "up_count": up,
        "down_count": down,
        "breadth": breadth,
        "score": score,
        "leader": {
            "ticker": f"{leader_prefix}{leader_code}" if leader_code else None,
            "name": row.get("f128"),
            "today_change_percent": _number(row.get("f136")),
        },
    }


def _return(closes: list[float], days: int) -> float | None:
    if len(closes) <= days or closes[-days - 1] <= 0:
        return None
    return round((closes[-1] / closes[-days - 1] - 1) * 100, 2)


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    try:
        parsed = float(str(value))
        return parsed if math.isfinite(parsed) else None
    except Exception:
        return None
