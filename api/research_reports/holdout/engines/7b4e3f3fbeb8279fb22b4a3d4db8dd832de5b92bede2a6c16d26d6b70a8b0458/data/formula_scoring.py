"""Pure versioned formula shared by live ranking and chronological backtests."""
from __future__ import annotations
import math
from typing import Any, Literal

FormulaMode = Literal["balanced", "conservative", "aggressive"]
VERSION = "formula-v2"
FACTORS = {
    "5日动量": ("change_5d", [(-12, 15), (-3, 42), (2, 78), (8, 92), (18, 48)]),
    "20日趋势": ("change_20d", [(-20, 18), (0, 50), (8, 82), (25, 92), (45, 50)]),
    "60日趋势": ("change_60d", [(-20, 20), (0, 45), (8, 78), (30, 92), (60, 58)]),
    "今日动量": ("today_change_percent", [(-10, 10), (-2, 45), (1, 72), (5, 90), (9.5, 58)]),
    "量比": ("volume_ratio", [(0, 30), (0.8, 58), (1.2, 80), (2.5, 92), (5, 62)]),
    "换手率": ("turnover_rate", [(0, 25), (1, 55), (3, 82), (8, 92), (18, 55)]),
}
WEIGHTS = {
    "balanced": dict(zip([*FACTORS, "估值", "市值质量"], [.20, .25, .15, .10, .10, .08, .05, .07])),
    "conservative": dict(zip([*FACTORS, "估值", "市值质量"], [.10, .20, .15, .05, .05, .05, .20, .20])),
    "aggressive": dict(zip([*FACTORS, "估值", "市值质量"], [.25, .25, .15, .10, .12, .08, .02, .03])),
}
CAP_TIERS = {"CN": (5, 80, 300, 1000), "HK": (5, 85, 330, 1100), "US": (1, 12, 45, 150)}  # native currency billions, research thresholds

def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None

def range_score(value: float | None, points: list[tuple[float, float]]) -> float:
    if value is None:
        return 0
    if value <= points[0][0]:
        return points[0][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return points[-1][1]

def valuation_score(pe: float | None, pb: float | None) -> float:
    pe_score = 0 if pe is None else 20 if pe <= 0 else max(20, min(92, 100 - abs(pe - 28) * 1.4))
    pb_score = 0 if pb is None else 20 if pb <= 0 else max(20, min(90, 95 - abs(pb - 3) * 8))
    return pe_score * .65 + pb_score * .35

def cap_score(cap: float | None, market: str = "CN") -> float:
    if cap is None or cap <= 0:
        return 0
    billions = cap / 1_000_000_000
    minimum, small, medium, large = CAP_TIERS.get(market, CAP_TIERS["CN"])
    return 88 if minimum <= billions <= small else 78 if small < billions <= medium else 68 if medium < billions <= large else 58 if billions > large else 52

def cap_label(cap: float | None, market: str = "CN") -> str:
    _, small, medium, _ = CAP_TIERS.get(market, CAP_TIERS["CN"])
    return "未知市值" if cap is None or cap <= 0 else "小盘" if cap < small * 1e9 else "中盘" if cap < medium * 1e9 else "大盘"

def describe(mode: FormulaMode = "balanced") -> str:
    return " + ".join(f"{key}{weight:.0%}" for key, weight in WEIGHTS[mode].items()) + " - 追高与异常估值惩罚；缺失因子贡献为0，不重分配权重"

def score_item(item: dict[str, Any], mode: FormulaMode = "balanced", weights: dict[str, float] | None = None) -> dict[str, Any]:
    from investment.data.formula_risk import history_timing, risk_plan
    item = dict(item)
    history_date = item.get("history_as_of")
    if history_date is None and item.get("risk_bars"):
        history_date = item["risk_bars"][-1].get("date")
    timing = history_timing(item, history_date)
    if timing["status"] not in ("ok", "unverified"):
        for field in ("change_5d", "change_20d", "change_60d"):
            item[field] = None
        item["history_error"] = timing["reason"]
    weights = dict(weights or WEIGHTS[mode])
    if set(weights) != set(WEIGHTS[mode]) or any(number(value) is None or value < 0 for value in weights.values()) or not math.isclose(sum(weights.values()), 1, abs_tol=1e-8):
        raise ValueError("Factor weights must be finite, nonnegative and sum to one")
    fields = [field for field, _ in FACTORS.values()] + ["pe_ratio", "pb_ratio", "market_cap"]
    values = {field: number(item.get(field)) for field in fields}
    # Invalid physical metrics are unavailable, negative earnings PE stays valid.
    for field in ("market_cap", "volume_ratio", "turnover_rate"):
        if values[field] is not None and values[field] < 0:
            values[field] = None
    if values["market_cap"] == 0:
        values["market_cap"] = None
    components = {name: range_score(values[field], points) for name, (field, points) in FACTORS.items()}
    market = str(item.get("market") or "CN").upper()
    components.update({"估值": valuation_score(values["pe_ratio"], values["pb_ratio"]), "市值质量": cap_score(values["market_cap"], market)})
    availability = {name: float(values[field] is not None) for name, (field, _) in FACTORS.items()}
    availability.update({"估值": .65 * (values["pe_ratio"] is not None) + .35 * (values["pb_ratio"] is not None), "市值质量": float(values["market_cap"] is not None)})
    coverage = round(sum(weights[name] * availability[name] for name in weights), 4)
    penalty = 0.0
    risks = []
    if timing["status"] not in ("ok", "unverified"):
        risks.append(timing["reason"])
    if values["today_change_percent"] is not None and values["today_change_percent"] >= 9.5:
        penalty += 12; risks.append("当日接近涨停，注意追高与成交风险" if item.get("market", "CN") == "CN" else "单日涨幅较大，注意追高与波动风险")
    if values["pe_ratio"] is not None and (values["pe_ratio"] <= 0 or values["pe_ratio"] > 180):
        penalty += 8; risks.append("亏损或极高估值，需核对财报")
    if values["turnover_rate"] is not None and values["turnover_rate"] >= 15:
        risks.append("换手率偏高，短线波动可能放大")
    penalty *= 1.25 if mode == "conservative" else .75 if mode == "aggressive" else 1
    penalty = round(penalty, 4)
    contributions = {name: round(components[name] * weights[name], 4) for name in weights}
    score = round(max(0, min(100, sum(contributions.values()) - penalty)), 1)
    missing = [field for field in fields if values[field] is None]
    if missing:
        risks.append("部分指标缺失，分数不可与完整数据等同解释")
    recommendation = "数据不足" if coverage < .65 else "优先关注" if score >= 78 and penalty <= 15 and coverage >= .9 else "观察" if score >= 65 else "仅跟踪" if score >= 50 else "低分候选"
    reasons = [f"{name}贡献 {contributions[name]:.1f} 分" for name in sorted(contributions, key=contributions.get, reverse=True)[:3] if contributions[name] > 0]
    from investment.data.formula_risk import risk_plan
    plan = risk_plan(item, item.get("risk_bars") or [], mode)
    clean_item = {key: value for key, value in item.items() if key != "risk_bars"}
    return {**clean_item, **values, "risk_plan": plan, "market_cap_currency": {"CN": "CNY", "HK": "HKD", "US": "USD"}.get(market), "theme": item.get("theme") or cap_label(values["market_cap"], market), "formula_version": VERSION, "formula_score": score, "recommendation": recommendation, "original_score": None, "components": {**{key: round(value, 4) for key, value in components.items()}, "风险惩罚": penalty}, "contributions": contributions, "weights": weights, "data_coverage": coverage, "missing_fields": missing, "reasons": reasons, "risks": risks or ["量化初筛，需结合公告和基本面确认"], "action": "结合公告、财务和板块强度进一步确认"}
