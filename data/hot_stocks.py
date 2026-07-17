"""Explainable hot-stock ranking across CN, HK, and US markets."""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable

import requests

from investment.data.market_scanner import scan_cn_market


CACHE_SECONDS = 600
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "storage" / "market"
_cache_lock = Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _number(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("raw")
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _percentiles(values: list[float]) -> dict[float, float]:
    unique = sorted(set(values))
    if len(unique) <= 1:
        return {value: 100.0 for value in unique}
    return {
        value: round(index / (len(unique) - 1) * 100, 4)
        for index, value in enumerate(unique)
    }


def _normalized_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or row.get("symbol") or "").strip()
    name = str(row.get("name") or ticker).strip()
    price = _number(row.get("price"))
    amount = _number(row.get("amount"))
    if amount is None:
        turnover = _number(row.get("turnover_rate"))
        float_market_cap = _number(row.get("float_market_cap")) or _number(row.get("market_cap"))
        if turnover is not None and float_market_cap is not None:
            amount = float_market_cap * turnover / 100
    change = _number(row.get("today_change_percent"))
    if change is None:
        change = _number(row.get("change_percent"))
    if not ticker or not name or price is None or price <= 0 or amount is None or amount <= 0:
        return None
    upper_name = name.upper().strip()
    if upper_name.startswith(("ST", "*ST")) or "退" in name:
        return None
    return {
        **row,
        "ticker": ticker,
        "name": name,
        "price": price,
        "amount": amount,
        "today_change_percent": change or 0.0,
        "turnover_rate": _number(row.get("turnover_rate")),
        "volume_ratio": _number(row.get("volume_ratio")),
    }


def rank_hot_stocks(
    rows: list[dict[str, Any]],
    mode: str = "hot",
    limit: int = 6,
) -> list[dict[str, Any]]:
    if mode not in {"hot", "amount", "gainers"}:
        raise ValueError("Unsupported hot-stock ranking mode")
    candidates = [candidate for row in rows if (candidate := _normalized_candidate(row))]
    if len(candidates) >= 10:
        amounts = sorted(float(item["amount"]) for item in candidates)
        threshold = amounts[int((len(amounts) - 1) * 0.10)]
        candidates = [item for item in candidates if float(item["amount"]) > threshold]
    if not candidates:
        return []

    factor_values: dict[str, list[float]] = {
        "amount": [float(item["amount"]) for item in candidates],
        "movement": [min(abs(float(item["today_change_percent"])), 20.0) for item in candidates],
        "turnover": [float(item["turnover_rate"]) for item in candidates if item["turnover_rate"] is not None],
        "volume_ratio": [float(item["volume_ratio"]) for item in candidates if item["volume_ratio"] is not None],
    }
    ranks = {factor: _percentiles(values) for factor, values in factor_values.items()}
    weights = {"amount": 0.45, "movement": 0.25, "turnover": 0.20, "volume_ratio": 0.10}

    ranked: list[dict[str, Any]] = []
    for item in candidates:
        raw_factors = {
            "amount": float(item["amount"]),
            "movement": min(abs(float(item["today_change_percent"])), 20.0),
            "turnover": item["turnover_rate"],
            "volume_ratio": item["volume_ratio"],
        }
        components = {
            factor: ranks[factor][float(value)]
            for factor, value in raw_factors.items()
            if value is not None and ranks[factor]
        }
        available_weight = sum(weights[factor] for factor in components)
        heat_score = (
            sum(components[factor] * weights[factor] for factor in components) / available_weight
            if available_weight
            else 0.0
        )
        ranked.append(
            {
                **item,
                "heat_score": round(heat_score, 2),
                "score_components": {factor: round(value, 2) for factor, value in components.items()},
            }
        )

    sort_key = {
        "hot": lambda item: (item["heat_score"], item["amount"]),
        "amount": lambda item: (item["amount"], item["heat_score"]),
        "gainers": lambda item: (item["today_change_percent"], item["amount"]),
    }[mode]
    ranked.sort(key=sort_key, reverse=True)
    return ranked[: max(0, limit)]


def load_hot_stock_snapshot(
    market: str,
    fetch_rows: Callable[[], list[dict[str, Any]]],
    snapshot_path: Path,
    source: str | None = None,
) -> dict[str, Any]:
    try:
        rows = fetch_rows()
        if not rows:
            raise RuntimeError("Hot-stock provider returned no rows")
        return {
            "market": market,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": source or f"{market} live market data",
            "stale": False,
            "rows": rows,
        }
    except Exception:
        if not snapshot_path.exists():
            raise
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            raise RuntimeError(f"No valid {market} hot-stock snapshot is available")
        return {
            "market": market,
            "generated_at": payload.get("generated_at"),
            "source": payload.get("source") or f"{market} saved snapshot",
            "stale": True,
            "rows": rows,
        }


def _cn_rows() -> list[dict[str, Any]]:
    return list(scan_cn_market()["rows"])


def _yahoo_active_rows(market: str) -> list[dict[str, Any]]:
    region = "HK" if market == "HK" else "US"
    response = requests.get(
        "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved",
        params={
            "scrIds": "most_actives",
            "count": 100,
            "formatted": "false",
            "region": region,
            "lang": "zh-Hant-HK" if market == "HK" else "en-US",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=12,
    )
    response.raise_for_status()
    finance = response.json().get("finance") or {}
    result = (finance.get("result") or [{}])[0]
    quotes = result.get("quotes") or []
    rows = []
    for quote in quotes:
        symbol = str(quote.get("symbol") or "")
        price = _number(quote.get("regularMarketPrice"))
        volume = _number(quote.get("regularMarketVolume"))
        average_volume = _number(quote.get("averageDailyVolume3Month"))
        if market == "HK":
            code = symbol.upper().replace(".HK", "").zfill(5)
            ticker = f"hk{code}"
        else:
            ticker = symbol.upper()
        rows.append(
            {
                "ticker": ticker,
                "name": quote.get("longName") or quote.get("shortName") or ticker,
                "market": market,
                "price": price,
                "amount": price * volume if price and volume else None,
                "today_change_percent": _number(quote.get("regularMarketChangePercent")),
                "turnover_rate": None,
                "volume_ratio": volume / average_volume if volume and average_volume else None,
            }
        )
    return [row for row in rows if row["price"] and row["amount"]]


def get_hot_stock_snapshot(market: str) -> dict[str, Any]:
    normalized_market = market.upper()
    if normalized_market not in {"CN", "HK", "US"}:
        raise ValueError("market must be CN, HK, or US")
    now = time.time()
    with _cache_lock:
        cached = _cache.get(normalized_market)
        if cached and now < cached[0]:
            return dict(cached[1])

    if normalized_market == "CN":
        fetch_rows = _cn_rows
        snapshot_path = SNAPSHOT_DIR / "latest.json"
        source = "Eastmoney A-share market snapshot"
    else:
        fetch_rows = lambda: _yahoo_active_rows(normalized_market)
        snapshot_path = SNAPSHOT_DIR / f"hot-{normalized_market.lower()}.json"
        source = f"Yahoo Finance {normalized_market} most active"
    snapshot = load_hot_stock_snapshot(
        normalized_market,
        fetch_rows=fetch_rows,
        snapshot_path=snapshot_path,
        source=source,
    )
    with _cache_lock:
        _cache[normalized_market] = (now + CACHE_SECONDS, snapshot)
    return dict(snapshot)
