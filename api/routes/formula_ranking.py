"""Formula-based stock ranking for the Vercel lite deployment."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Query

from investment.data.market_scanner import enrich_stock_history, scan_cn_market
from investment.data.stock_picker import CANDIDATE_POOL, PROJECT_ROOT


router = APIRouter()

FormulaMode = Literal["balanced", "conservative", "aggressive"]

FORMULA_DESCRIPTION = (
    "全市场初筛后补算日K：5日动量20% + 20日趋势25% + 60日趋势15% + 今日动量10% "
    "+ 量比10% + 换手率8% + 估值5% + 市值质量7% - 追高与异常估值惩罚"
)


@router.get("/formula-ranking")
async def formula_ranking(
    market: str = Query("CN", description="Market filter: CN, US, HK, all"),
    limit: int = Query(30, ge=1, le=100),
    mode: FormulaMode = Query("balanced", description="Risk mode"),
):
    if market.upper() == "CN":
        try:
            scan = scan_cn_market()
            ranked = [_rank_live_item(item, mode) for item in scan["rows"]]
            ranked.sort(key=lambda item: item["formula_score"], reverse=True)
            return {
                "status": "ok",
                "result": {
                    "generated_at": scan["generated_at"],
                    "market": "CN",
                    "mode": mode,
                    "formula": FORMULA_DESCRIPTION,
                    "items": ranked[:limit],
                    "total": len(ranked),
                    "scanned_count": len(scan["rows"]),
                    "history_enriched_count": 0,
                    "cached": scan["cached"],
                    "fallback": False,
                    "source": "东方财富沪深 A 股全市场快照（10分钟缓存）",
                },
            }
        except Exception as exc:
            fallback_error = str(exc)
    else:
        fallback_error = None

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
            "scanned_count": len(rows),
            "cached": True,
            "fallback": True,
            "fallback_reason": fallback_error,
            "source": "历史候选缓存 + 固定公式排序（全市场行情不可用时降级）",
        },
    }


@router.get("/formula-ranking/history")
async def formula_ranking_history(
    tickers: str = Query(..., min_length=1),
    mode: FormulaMode = Query("balanced"),
):
    wanted = [item.strip() for item in tickers.split(",") if item.strip()][:30]
    scan = scan_cn_market()
    wanted_set = set(wanted)
    selected = [item for item in scan["rows"] if item.get("ticker") in wanted_set]
    enriched_rows = enrich_stock_history(selected, limit=len(selected))
    enriched = [
        item
        for item in enriched_rows
        if all(isinstance(item.get(key), (int, float)) for key in ("change_5d", "change_20d", "change_60d"))
    ]
    ranked = [_rank_live_item(item, mode) for item in enriched]
    ranked.sort(key=lambda item: item["formula_score"], reverse=True)
    return {
        "status": "ok",
        "result": {
            "items": ranked,
            "history_enriched_count": len(ranked),
            "requested_count": len(wanted),
        },
    }


def _rank_live_item(item: dict[str, Any], mode: FormulaMode) -> dict[str, Any]:
    change_today = _num(item.get("today_change_percent"))
    change_5d = _num(item.get("change_5d"))
    change_20d = _num(item.get("change_20d"))
    change_60d = _num(item.get("change_60d"))
    volume_ratio = _num(item.get("volume_ratio"))
    turnover = _num(item.get("turnover_rate"))
    pe_ratio = _num(item.get("pe_ratio"))
    pb_ratio = _num(item.get("pb_ratio"))
    market_cap = _num(item.get("market_cap"))

    components = {
        "5日动量": _range_score(change_5d, [(-12, 15), (-3, 42), (2, 78), (8, 92), (18, 48)]),
        "20日趋势": _range_score(change_20d, [(-20, 18), (0, 50), (8, 82), (25, 92), (45, 50)]),
        "60日趋势": _range_score(change_60d, [(-20, 20), (0, 45), (8, 78), (30, 92), (60, 58)]),
        "今日动量": _range_score(change_today, [(-10, 10), (-2, 45), (1, 72), (5, 90), (9.5, 58)]),
        "量比": _range_score(volume_ratio, [(0, 30), (0.8, 58), (1.2, 80), (2.5, 92), (5, 62)]),
        "换手率": _range_score(turnover, [(0, 25), (1, 55), (3, 82), (8, 92), (18, 55)]),
        "估值": _valuation_score(pe_ratio, pb_ratio),
        "市值质量": _market_cap_score(market_cap),
    }
    penalty = 0.0
    if change_today is not None and change_today >= 9.5:
        penalty += 12
    if pe_ratio is not None and (pe_ratio < 0 or pe_ratio > 180):
        penalty += 8
    if mode == "conservative":
        penalty *= 1.25
        components["市值质量"] = min(100, components["市值质量"] + 8)
    elif mode == "aggressive":
        penalty *= 0.75
        components["量比"] = min(100, components["量比"] + 5)
        components["换手率"] = min(100, components["换手率"] + 5)

    weighted = (
        components["5日动量"] * 0.20
        + components["20日趋势"] * 0.25
        + components["60日趋势"] * 0.15
        + components["今日动量"] * 0.10
        + components["量比"] * 0.10
        + components["换手率"] * 0.08
        + components["估值"] * 0.05
        + components["市值质量"] * 0.07
        - penalty
    )
    score = round(max(0, min(weighted, 100)), 1)
    return {
        **item,
        "theme": _market_cap_label(market_cap),
        "formula_score": score,
        "recommendation": _recommendation(score, penalty),
        "original_score": None,
        "components": {**{key: round(value, 1) for key, value in components.items()}, "风险惩罚": round(penalty, 1)},
        "risks": _live_risks(item),
        "action": "结合公告、财务和板块强度进一步确认",
    }


def _range_score(value: float | None, points: list[tuple[float, float]]) -> float:
    if value is None:
        return 40
    if value <= points[0][0]:
        return points[0][1]
    for (left_x, left_y), (right_x, right_y) in zip(points, points[1:]):
        if value <= right_x:
            ratio = (value - left_x) / (right_x - left_x)
            return left_y + (right_y - left_y) * ratio
    return points[-1][1]


def _valuation_score(pe_ratio: float | None, pb_ratio: float | None) -> float:
    pe_score = 35 if pe_ratio is None or pe_ratio <= 0 else max(20, min(92, 100 - abs(pe_ratio - 28) * 1.4))
    pb_score = 40 if pb_ratio is None or pb_ratio <= 0 else max(20, min(90, 95 - abs(pb_ratio - 3) * 8))
    return pe_score * 0.65 + pb_score * 0.35


def _market_cap_score(value: float | None) -> float:
    if value is None or value <= 0:
        return 35
    cap_billion = value / 1_000_000_000
    if 5 <= cap_billion <= 80:
        return 88
    if 80 < cap_billion <= 300:
        return 78
    if 300 < cap_billion <= 1000:
        return 68
    if cap_billion > 1000:
        return 58
    return 52


def _market_cap_label(value: float | None) -> str:
    if value is None:
        return "未知市值"
    cap_billion = value / 1_000_000_000
    if cap_billion < 80:
        return "小盘成长"
    if cap_billion < 300:
        return "中盘"
    return "大盘"


def _live_risks(item: dict[str, Any]) -> list[str]:
    risks: list[str] = []
    if (_num(item.get("today_change_percent")) or 0) >= 9.5:
        risks.append("当日接近涨停，注意追高风险")
    if (_num(item.get("turnover_rate")) or 0) >= 15:
        risks.append("换手率偏高，短线波动可能放大")
    pe = _num(item.get("pe_ratio"))
    if pe is not None and (pe < 0 or pe > 100):
        risks.append("盈利或估值指标偏激进")
    return risks or ["公式仅做量化初筛，需结合公告和基本面确认"]


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
