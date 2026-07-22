"""A-share equity-sector ETF discovery and heat ranking."""
from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable

import requests


ETF_LIST_URLS = [
    "https://push2delay.eastmoney.com/api/qt/clist/get",
    "https://push2.eastmoney.com/api/qt/clist/get",
]
ETF_FILTER = "b:MK0021,b:MK0022,b:MK0023,b:MK0024,b:MK0827"
ETF_FIELDS = "f2,f3,f5,f6,f8,f10,f12,f14"
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "storage" / "market" / "hot-etfs.json"
CACHE_SECONDS = 600
_cache_lock = Lock()
_cache: tuple[float, dict[str, Any]] | None = None


THEME_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("半导体", ("半导体", "芯片", "集成电路")),
    ("人工智能", ("人工智能", "AI", "算力", "云计算", "软件")),
    ("机器人", ("机器人", "工业母机", "智能制造")),
    ("医药医疗", ("医药", "医疗", "创新药", "生物科技")),
    ("新能源", ("新能源", "光伏", "锂电", "电池", "储能", "风电")),
    ("消费", ("消费", "食品饮料", "酒", "家电")),
    ("军工", ("军工", "国防", "航空航天")),
    ("证券", ("证券", "券商")),
    ("银行", ("银行",)),
    ("红利", ("红利", "高股息")),
    ("通信", ("通信", "5G")),
    ("汽车", ("汽车", "智能车", "车联网")),
    ("有色金属", ("有色", "稀土", "钢铁", "煤炭")),
    ("农业", ("农业", "养殖", "畜牧")),
    ("传媒", ("传媒", "游戏", "影视")),
)

EXCLUDED_KEYWORDS = (
    "货币", "现金", "理财", "债", "国债", "信用", "黄金", "商品", "原油",
    "QDII", "纳指", "纳斯达克", "恒生", "日经", "标普", "德国", "法国",
    "杠杆", "反向", "两倍", "沪深300", "中证500", "中证1000", "上证50",
    "科创50", "创业板", "A500", "全指", "宽基",
)


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def _percentiles(values: list[float]) -> dict[float, float]:
    unique = sorted(set(values))
    if len(unique) <= 1:
        return {value: 100.0 for value in unique}
    return {value: index / (len(unique) - 1) * 100 for index, value in enumerate(unique)}


def theme_for_etf(name: str, category: str | None = None) -> str | None:
    text = f"{category or ''} {name}".upper()
    if any(keyword.upper() in text for keyword in EXCLUDED_KEYWORDS):
        return None
    for theme, keywords in THEME_KEYWORDS:
        if any(keyword.upper() in text for keyword in keywords):
            return theme
    return None


def rank_hot_etf_sectors(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        theme = theme_for_etf(str(row.get("name") or ""), str(row.get("category") or ""))
        price = _number(row.get("price"))
        amount = _number(row.get("amount"))
        daily_return = _number(row.get("today_change_percent"))
        turnover = _number(row.get("turnover_rate"))
        volume_ratio = _number(row.get("volume_ratio"))
        if not theme or price is None or price <= 0 or amount is None or amount <= 0 or daily_return is None:
            continue
        candidates.append(
            {
                **row,
                "theme": theme,
                "price": price,
                "amount": amount,
                "today_change_percent": daily_return,
                "turnover_rate": turnover,
                "volume_ratio": volume_ratio,
                "change_5d": _number(row.get("change_5d")),
                "activity": turnover if turnover is not None else volume_ratio,
            }
        )
    if not candidates:
        return []

    values = {
        "amount": [float(item["amount"]) for item in candidates],
        "return": [float(item["today_change_percent"]) for item in candidates],
        "activity": [float(item["activity"]) for item in candidates if item["activity"] is not None],
        "momentum": [float(item["change_5d"]) for item in candidates if item["change_5d"] is not None],
    }
    ranks = {factor: _percentiles(factor_values) for factor, factor_values in values.items()}
    weights = {"amount": 0.40, "return": 0.30, "activity": 0.20, "momentum": 0.10}
    scored = []
    for item in candidates:
        raw = {
            "amount": item["amount"],
            "return": item["today_change_percent"],
            "activity": item["activity"],
            "momentum": item["change_5d"],
        }
        components = {
            factor: ranks[factor][float(value)]
            for factor, value in raw.items()
            if value is not None and ranks[factor]
        }
        available_weight = sum(weights[factor] for factor in components)
        score = sum(components[factor] * weights[factor] for factor in components) / available_weight
        scored.append(
            {
                **item,
                "heat_score": round(score, 2),
                "score_components": {factor: round(value, 2) for factor, value in components.items()},
            }
        )

    representatives: dict[str, dict[str, Any]] = {}
    for item in scored:
        current = representatives.get(item["theme"])
        if current is None or item["amount"] > current["amount"]:
            representatives[item["theme"]] = item
    result = list(representatives.values())
    result.sort(key=lambda item: (item["heat_score"], item["amount"]), reverse=True)
    return result[: max(0, limit)]


def load_hot_etf_snapshot(
    fetch_rows: Callable[[], list[dict[str, Any]]],
    snapshot_path: Path = SNAPSHOT_PATH,
) -> dict[str, Any]:
    try:
        rows = fetch_rows()
        if not rows:
            raise RuntimeError("ETF provider returned no rows")
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "Eastmoney A-share ETF market",
            "stale": False,
            "rows": rows,
        }
    except Exception:
        if not snapshot_path.exists():
            raise
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("No valid A-share ETF snapshot is available")
        return {
            "generated_at": payload.get("generated_at"),
            "source": payload.get("source") or "saved A-share ETF snapshot",
            "stale": True,
            "rows": rows,
        }


def _fetch_page(page: int) -> dict[str, Any]:
    params = {
        "pn": page,
        "pz": 100,
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f6",
        "fs": ETF_FILTER,
        "fields": ETF_FIELDS,
    }
    last_error: Exception | None = None
    for url in ETF_LIST_URLS:
        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
                timeout=12,
            )
            response.raise_for_status()
            data = response.json().get("data")
            if isinstance(data, dict):
                return data
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Unable to fetch ETF page {page}: {last_error}")


def fetch_cn_etfs() -> list[dict[str, Any]]:
    first = _fetch_page(1)
    total = int(first.get("total") or 0)
    rows = list(first.get("diff") or [])
    pages = max(1, math.ceil(total / 100))
    if pages > 1:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(_fetch_page, page) for page in range(2, pages + 1)]
            for future in as_completed(futures):
                rows.extend(future.result().get("diff") or [])
    result = []
    for row in rows:
        code = str(row.get("f12") or "")
        name = str(row.get("f14") or "").strip()
        if not code or not name:
            continue
        result.append(
            {
                "ticker": f"{'sh' if code.startswith('5') else 'sz'}{code}",
                "name": name,
                "market": "CN",
                "price": _number(row.get("f2")),
                "amount": _number(row.get("f6")),
                "today_change_percent": _number(row.get("f3")),
                "turnover_rate": _number(row.get("f8")),
                "volume_ratio": _number(row.get("f10")),
            }
        )
    if len(result) < 500:
        raise RuntimeError(f"A-share ETF snapshot is incomplete: {len(result)}")
    return result


def get_hot_etf_snapshot() -> dict[str, Any]:
    global _cache
    now = time.time()
    with _cache_lock:
        if _cache and now < _cache[0]:
            return dict(_cache[1])
    snapshot = load_hot_etf_snapshot(fetch_cn_etfs)
    with _cache_lock:
        _cache = (now + CACHE_SECONDS, snapshot)
    return dict(snapshot)
