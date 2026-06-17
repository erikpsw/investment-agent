"""Formula-based stock ranking for the Vercel lite deployment."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Query

from investment.data.stock_picker import CANDIDATE_POOL, PROJECT_ROOT


router = APIRouter()

FormulaMode = Literal["balanced", "conservative", "aggressive"]

FORMULA_DESCRIPTION = (
    "公式分 = 原始评分35% + 20日趋势20% + 5日动量15% + 距20日高点回撤15% "
    "+ 20日均线位置10% + 波动率5% + 标的属性加减分 - 追高/风险惩罚"
)


@router.get("/formula-ranking")
async def formula_ranking(
    market: str = Query("CN", description="Market filter: CN, US, HK, all"),
    limit: int = Query(30, ge=1, le=100),
    mode: FormulaMode = Query("balanced", description="Risk mode"),
):
    latest = _latest_result()
    rows = _collect_items(latest, market)
    ranked = [_rank_item(item, mode) for item in rows]
    ranked.sort(key=lambda item: item["formula_score"], reverse=True)
    return {
        "status": "ok",
        "result": {
            "generated_at": latest.get("generated_at") if isinstance(latest, dict) else None,
            "market": market,
            "mode": mode,
            "formula": FORMULA_DESCRIPTION,
            "items": ranked[:limit],
            "total": len(ranked),
            "source": "最近一次选股缓存 + 固定公式排序",
        },
    }


def _latest_result() -> dict[str, Any]:
    path = Path(PROJECT_ROOT) / "storage" / "stock_picker" / "results.jsonl"
    if not path.exists():
        return {}
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return {}
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _collect_items(latest: dict[str, Any], market: str) -> list[dict[str, Any]]:
    wanted = market.upper()
    by_ticker: dict[str, dict[str, Any]] = {}
    for group in ("recommendations", "watch_only", "avoid"):
        for item in latest.get(group, []) if isinstance(latest, dict) else []:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "")
            if not ticker:
                continue
            item_market = str(item.get("market") or "").upper()
            if wanted != "ALL" and item_market != wanted:
                continue
            row = dict(item)
            row["source_group"] = group
            by_ticker[ticker] = row

    if by_ticker:
        return list(by_ticker.values())

    for base in CANDIDATE_POOL:
        item_market = str(base.get("market") or "").upper()
        if wanted != "ALL" and item_market != wanted:
            continue
        by_ticker[str(base.get("ticker"))] = dict(base)
    return list(by_ticker.values())


def _rank_item(item: dict[str, Any], mode: FormulaMode) -> dict[str, Any]:
    original = _num(item.get("score"))
    change_20d = _num(item.get("change_20d"))
    change_5d = _num(item.get("change_5d"))
    distance_high = _num(item.get("distance_to_high_20d"))
    distance_ma20 = _num(item.get("distance_to_ma20"))
    volatility = _num(item.get("volatility_20d"))
    today_change = _num(item.get("today_change_percent"))

    components = {
        "原始评分": _original_component(original, item),
        "20日趋势": _trend_component(change_20d),
        "5日动量": _recent_component(change_5d),
        "回撤位置": _pullback_component(distance_high),
        "均线位置": _ma_component(distance_ma20),
        "波动率": _volatility_component(volatility),
        "标的属性": _profile_adjustment(item),
        "风险惩罚": _risk_penalty(item, today_change, mode),
    }

    weighted = (
        components["原始评分"] * 0.35
        + components["20日趋势"] * 0.20
        + components["5日动量"] * 0.15
        + components["回撤位置"] * 0.15
        + components["均线位置"] * 0.10
        + components["波动率"] * 0.05
        + components["标的属性"]
        - components["风险惩罚"]
    )
    formula_score = round(max(0, min(weighted, 100)), 1)
    recommendation = _recommendation(formula_score, components["风险惩罚"])

    return {
        "ticker": item.get("ticker"),
        "name": item.get("name"),
        "market": item.get("market"),
        "theme": item.get("theme"),
        "profile": item.get("profile"),
        "formula_score": formula_score,
        "recommendation": recommendation,
        "original_score": original,
        "price": item.get("price"),
        "change_5d": change_5d,
        "change_20d": change_20d,
        "distance_to_high_20d": distance_high,
        "distance_to_ma20": distance_ma20,
        "volatility_20d": volatility,
        "today_change_percent": today_change,
        "action": item.get("action"),
        "reasons": item.get("reasons") if isinstance(item.get("reasons"), list) else [],
        "risks": item.get("risks") if isinstance(item.get("risks"), list) else [],
        "components": {key: round(value, 1) for key, value in components.items()},
    }


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except Exception:
        return None


def _original_component(value: float | None, item: dict[str, Any]) -> float:
    if value is not None:
        return max(0, min(value, 100))
    return {
        "emerging": 58,
        "core": 54,
        "mega": 44,
        "defensive": 42,
    }.get(str(item.get("profile") or ""), 50)


def _trend_component(value: float | None) -> float:
    if value is None:
        return 50
    if 3 <= value <= 18:
        return 88
    if 0 <= value < 3:
        return 68
    if 18 < value <= 28:
        return 62
    if value > 28:
        return 35
    if -8 <= value < 0:
        return 45
    return 25


def _recent_component(value: float | None) -> float:
    if value is None:
        return 50
    if -2 <= value <= 8:
        return 85
    if 8 < value <= 12:
        return 62
    if value > 12:
        return 30
    if -8 <= value < -2:
        return 55
    return 28


def _pullback_component(value: float | None) -> float:
    if value is None:
        return 50
    if -12 <= value <= -3:
        return 90
    if -3 < value <= 0:
        return 62
    if -20 <= value < -12:
        return 65
    if value < -20:
        return 35
    return 45


def _ma_component(value: float | None) -> float:
    if value is None:
        return 50
    if -3 <= value <= 6:
        return 86
    if 6 < value <= 12:
        return 60
    if value > 12:
        return 35
    if -10 <= value < -3:
        return 55
    return 30


def _volatility_component(value: float | None) -> float:
    if value is None:
        return 50
    if value <= 3:
        return 88
    if value <= 5:
        return 72
    if value <= 8:
        return 45
    return 25


def _profile_adjustment(item: dict[str, Any]) -> float:
    return {
        "emerging": 4,
        "core": 2,
        "mega": -6,
        "defensive": -4,
    }.get(str(item.get("profile") or ""), 0)


def _risk_penalty(item: dict[str, Any], today_change: float | None, mode: FormulaMode) -> float:
    text = " ".join(
        [
            str(item.get("action") or ""),
            " ".join(str(value) for value in item.get("risks", []) if value),
        ]
    )
    penalty = 0.0
    if "回避" in text:
        penalty += 18
    if any(word in text for word in ("追高", "短线涨幅", "高点")):
        penalty += 10
    if today_change is not None and today_change >= 7:
        penalty += 8
    if mode == "conservative":
        penalty *= 1.25
    elif mode == "aggressive":
        penalty *= 0.75
    return penalty


def _recommendation(score: float, risk_penalty: float) -> str:
    if score >= 78 and risk_penalty <= 15:
        return "优先关注"
    if score >= 65:
        return "观察等买点"
    if score >= 50:
        return "仅跟踪"
    return "暂不推荐"

