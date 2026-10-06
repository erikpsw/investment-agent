"""Lightweight full-market A-share scanner for the Vercel deployment."""
from __future__ import annotations

import json
import math
import re
import time
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
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
_history_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "storage" / "market" / "latest.json"


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
    if len(filtered) < 2500:
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
    if not isinstance(rows, list):
        return None
    rows = [row for row in rows if _is_main_board_ticker(str(row.get("ticker") or ""))]
    if len(rows) < 2500:
        return None
    return {
        "rows": rows,
        "generated_at": payload.get("generated_at"),
        "cached": True,
        "source": "GitHub Actions 交易日全市场快照",
    }


def enrich_stock_history(rows: list[dict[str, Any]], limit: int = 120, as_of: str | None = None) -> list[dict[str, Any]]:
    selected = sorted(rows, key=_snapshot_priority, reverse=True)[:limit]
    by_ticker = {str(row["ticker"]): {**row, "quote_as_of": as_of} for row in selected}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_stock_returns, ticker, as_of): ticker for ticker in by_ticker}
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


def _stock_returns(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"(?:sh|sz)\d{6}", ticker):
        raise ValueError("Invalid A-share history ticker")
    shanghai = timezone(timedelta(hours=8))
    end = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of else datetime.now(shanghai)
    if end.tzinfo is None:
        end = end.replace(tzinfo=shanghai)
    end = end.astimezone(shanghai)
    # A date-only argument means the completed date. Intraday snapshots cannot
    # use that day's as-yet-unknown closing K-line.
    if (not as_of or len(as_of) > 10) and end.hour < 15:
        end -= timedelta(days=1)
    cache_key = (ticker, end.strftime("%Y%m%d"))
    now = time.time()
    cached = _history_cache.get(cache_key)
    if cached and now < cached[0]:
        return dict(cached[1])
    from investment.data.foreign_formula import _validated_bars
    cache_path = ROOT / "storage/stock_picker/runtime-history" / f"{ticker}-{cache_key[1]}.json"
    try:
        saved = json.loads(cache_path.read_text(encoding="utf-8"))
        if saved.get("schema") == 1 and saved.get("ticker") == ticker and saved.get("cutoff") == cache_key[1]:
            cached_bars = _validated_bars(saved["bars"], end.date().isoformat())
            if cached_bars and len(cached_bars) == len(saved["bars"]):
                result = _history_features(cached_bars, saved["source"], saved["basis"])
                result["history_downloaded_at"] = saved["downloaded_at"]
                _history_cache[cache_key] = (now + CACHE_SECONDS, result)
                return dict(result)
    except (OSError, ValueError, KeyError, RuntimeError, TypeError):
        pass

    code = ticker[2:]
    secid = f"{'1' if ticker.startswith('sh') else '0'}.{code}"
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
    history_bars = []
    source, basis = "Eastmoney", "qfq"
    try:
        if data.get("code") and str(data["code"]) != code:
            raise RuntimeError("历史证券代码不匹配")
        candles = [str(item).split(",") for item in data.get("klines") or []]
        if any(len(candle) < 5 for candle in candles):
            raise RuntimeError("历史OHLC行不完整")
        history_bars = _validated_bars([{"date": candle[0], "open": _number(candle[1]), "close": _number(candle[2]), "high": _number(candle[3]), "low": _number(candle[4])} for candle in candles], end.date().isoformat())
    except (ValueError, RuntimeError, TypeError):
        history_bars = []
    if not history_bars:
        response = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get", params={"param": f"{ticker},day,,{end.date().isoformat()},120,qfq"}, timeout=8)
        response.raise_for_status()
        payload = response.json().get("data", {}).get(ticker, {})
        adjusted = payload.get("qfqday")
        raw = adjusted or payload.get("day") or []
        if any(len(row) < 5 for row in raw):
            raise RuntimeError("历史OHLC行不完整")
        history_bars = _validated_bars([{"date": row[0], "open": _number(row[1]), "close": _number(row[2]), "high": _number(row[3]), "low": _number(row[4])} for row in raw], end.date().isoformat())
        source, basis = "Tencent", "qfq" if adjusted else "raw"
    if not history_bars:
        raise RuntimeError(f"{ticker} 历史行情获取失败: {last_error}")
    result = _history_features(history_bars, source, basis)
    result["history_downloaded_at"] = datetime.now(timezone.utc).isoformat()
    temporary = cache_path.with_name(cache_path.name + f".{uuid4().hex}.tmp")
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps({"schema": 1, "ticker": ticker, "cutoff": cache_key[1], "downloaded_at": result["history_downloaded_at"], "source": source, "basis": basis, "bars": history_bars}, ensure_ascii=False), encoding="utf-8")
        temporary.replace(cache_path)
    except OSError:
        # Read-only serverless filesystems still use the validated memory cache.
        pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    _history_cache[cache_key] = (now + CACHE_SECONDS, result)
    return result


def _history_features(history_bars: list[dict], source: str, basis: str) -> dict:
    valid = [row["close"] for row in history_bars]
    return {
        "change_5d": _period_return(valid, 5),
        "change_20d": _period_return(valid, 20),
        "change_60d": _period_return(valid, 60),
        "history_as_of": history_bars[-1]["date"],
        "history_source": source,
        "history_price_basis": basis,
        "risk_bars": history_bars[-21:],
    }


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
    if not _is_main_board_code(code):
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
        "amount": amount,
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


def _is_main_board_ticker(ticker: str) -> bool:
    return len(ticker) >= 8 and ticker[:2] in {"sh", "sz"} and _is_main_board_code(ticker[2:])


def _is_main_board_code(code: str) -> bool:
    return code.startswith(("600", "601", "603", "605", "000", "001", "002", "003"))


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    try:
        parsed = float(str(value))
        return parsed if math.isfinite(parsed) else None
    except Exception:
        return None
