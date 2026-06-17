"""Fast sector/theme dashboard derived from the screened stock universe."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from investment.data.stock_picker import CANDIDATE_POOL, PROJECT_ROOT, _is_buyable_cn_ticker


router = APIRouter()


def _sector_name(theme: str) -> str:
    return str(theme or "其他").split("/")[0]


def _stock_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": item.get("ticker"),
        "name": item.get("name"),
        "market": item.get("market"),
        "theme": item.get("theme"),
        "score": item.get("score"),
        "change_5d": item.get("change_5d"),
        "change_20d": item.get("change_20d"),
    }


@router.get("/sectors")
async def list_sectors():
    results = _read_latest_results()
    latest = results[-1] if results else {}
    latest_items: dict[str, dict[str, Any]] = {}
    for group in ("recommendations", "watch_only", "avoid"):
        for item in latest.get(group, []) if isinstance(latest, dict) else []:
            if item.get("market") == "CN":
                latest_items[str(item.get("ticker"))] = item

    pools: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in CANDIDATE_POOL:
        if item.get("market") == "CN" and _is_buyable_cn_ticker(str(item.get("ticker"))):
            pools[_sector_name(str(item.get("theme")))].append(item)

    sectors = []
    for name, members in pools.items():
        scored = [latest_items[item["ticker"]] for item in members if item["ticker"] in latest_items]
        ranked = sorted(scored, key=lambda value: float(value.get("score") or 0), reverse=True)
        avg_5d = _average(ranked, "change_5d")
        avg_20d = _average(ranked, "change_20d")
        sectors.append(
            {
                "code": name,
                "name": name,
                "candidate_count": len(members),
                "scored_count": len(scored),
                "change_5d": avg_5d,
                "change_20d": avg_20d,
                "score": round(sum(float(item.get("score") or 0) for item in ranked) / len(ranked), 1) if ranked else None,
                "leader": _stock_summary(ranked[0] if ranked else members[0]),
                "stocks": [_stock_summary(item) for item in (ranked[:5] or members[:5])],
            }
        )
    sectors.sort(key=lambda value: (value["score"] is not None, value["score"] or -1, value["candidate_count"]), reverse=True)
    return {
        "status": "ok",
        "result": {
            "generated_at": latest.get("generated_at") if isinstance(latest, dict) else None,
            "sectors": sectors,
            "coverage_count": sum(len(items) for items in pools.values()),
            "source": "AI选股普通沪深主板候选池",
        },
    }


def _average(items: list[dict[str, Any]], key: str) -> float | None:
    values = [float(item[key]) for item in items if isinstance(item.get(key), (int, float))]
    return round(sum(values) / len(values), 2) if values else None


def _read_latest_results() -> list[dict[str, Any]]:
    path = Path(PROJECT_ROOT) / "storage" / "stock_picker" / "results.jsonl"
    if not path.exists():
        return []
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return []
    results: list[dict[str, Any]] = []
    for line in lines[-1:]:
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            results.append(value)
    return results
