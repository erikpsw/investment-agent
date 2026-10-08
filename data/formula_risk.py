"""Explainable long-only price scenarios, never executable orders or guarantees."""
from __future__ import annotations
import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from investment.data.formula_scoring import number

PARAMETERS = {
    "conservative": {"atr_multiple": 2.5, "risk_budget_percent": .5, "position_cap_percent": 10},
    "balanced": {"atr_multiple": 2, "risk_budget_percent": 1, "position_cap_percent": 20},
    "aggressive": {"atr_multiple": 1.5, "risk_budget_percent": 1, "position_cap_percent": 20},
}


def history_timing(item: dict, history_date: str | None) -> dict:
    quote = item.get("quote_as_of")
    if quote is None or history_date is None:
        return {"status": "unverified", "reason": "缺少报价或日K日期，未核验时间差"}
    try:
        if not isinstance(quote, str) or not isinstance(history_date, str):
            raise ValueError("Invalid date type")
        zone = ZoneInfo({"CN": "Asia/Shanghai", "HK": "Asia/Hong_Kong", "US": "America/New_York"}[str(item.get("market") or "CN").upper()])
        if len(quote) == 10:
            quote_day = date.fromisoformat(quote)
            if quote_day.isoformat() != quote:
                raise ValueError("Invalid quote date")
        else:
            stamp = datetime.fromisoformat(quote.replace("Z", "+00:00"))
            quote_day = (stamp.replace(tzinfo=zone) if stamp.tzinfo is None else stamp.astimezone(zone)).date()
        day = date.fromisoformat(history_date)
        if day.isoformat() != history_date:
            raise ValueError("Invalid history date")
    except (ValueError, TypeError, KeyError):
        return {"status": "invalid_quote_date", "reason": "报价或日K日期无效，无法核对保护价时间"}
    gap = (quote_day - day).days
    if gap < 0:
        return {"status": "future_history", "reason": "日K晚于报价日期，不能用于该报价的趋势或保护价", "history_lag_calendar_days": gap}
    # SSE/SZSE 2026 exchange closures; civil-service makeup weekends remain
    # closed. Unknown years/markets retain the conservative calendar-day guard.
    # https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml
    if str(item.get("market") or "CN").upper() == "CN" and day.year == quote_day.year == 2026:
        closures = [("01-01", "01-03"), ("02-15", "02-23"), ("04-04", "04-06"),
                    ("05-01", "05-05"), ("06-19", "06-21"), ("09-25", "09-27"), ("10-01", "10-07")]
        lag = sum(candidate.weekday() < 5 and not any(start <= candidate.strftime("%m-%d") <= end for start, end in closures)
                  for candidate in (day + timedelta(days=i) for i in range(1, gap + 1)))
        timing = {"history_lag_calendar_days": gap, "history_lag_trading_days": lag, "history_calendar": "SSE-SZSE-2026"}
        if lag > 5:
            return {"status": "stale_history", "reason": "日K落后报价超过5个交易日，暂停趋势与保护价参考", **timing}
        return {"status": "ok", **timing}
    if gap > 7:
        return {"status": "stale_history", "reason": "日K落后报价超过7个自然日，暂停趋势与保护价参考（含长假情况）", "history_lag_calendar_days": gap}
    return {"status": "ok", "history_lag_calendar_days": gap}


def risk_plan(item: dict, bars: list[dict], mode: str = "balanced", *, parameters: dict | None = None) -> dict:
    if mode not in PARAMETERS:
        raise ValueError("Unknown risk mode")
    settings = {**PARAMETERS[mode], "target_r": 1.5}
    if parameters:
        bounds = {"atr_multiple": (1, 4), "target_r": (1, 4), "risk_budget_percent": (.1, 2), "position_cap_percent": (1, 30)}
        for key, value in parameters.items():
            if key not in bounds or number(value) is None or not bounds[key][0] <= value <= bounds[key][1]:
                raise ValueError("Invalid research risk parameter")
        settings.update(parameters)
    market = str(item.get("market") or "CN").upper()
    currency = {"CN": "CNY", "HK": "HKD", "US": "USD"}.get(market)
    if currency is None:
        return {"status": "insufficient_data", "reason": "市场或币种未识别"}
    reference = number(item.get("price"))
    latest = bars[-21:]
    if reference is None or reference <= 0 or len(latest) < 21:
        return {"status": "insufficient_data", "reason": "需要正参考价与至少21条有效OHLC"}
    dates = [row.get("date") for row in latest]
    try:
        if any(date.fromisoformat(day).isoformat() != day for day in dates) or dates != sorted(set(dates)):
            raise ValueError("Invalid chronology")
    except (ValueError, TypeError):
        return {"status": "insufficient_data", "reason": "日K日期无效、重复或未按时间排序"}
    timing = history_timing(item, dates[-1])
    if timing["status"] not in ("ok", "unverified"):
        return timing
    prices = []
    for row in latest:
        values = {key: number(row.get(key)) for key in ("open", "high", "low", "close")}
        if any(value is None or value <= 0 for value in values.values()) or values["high"] < max(values["open"], values["close"], values["low"]) or values["low"] > min(values["open"], values["close"]):
            return {"status": "insufficient_data", "reason": "OHLC缺失或价格关系无效"}
        prices.append(values)
    if abs(reference / prices[-1]["close"] - 1) > .2:
        return {"status": "price_mismatch", "reason": "参考价与历史价偏离超过20%，请先核对复权、拆股或数据时间"}
    ranges = [max(today["high"] - today["low"], abs(today["high"] - previous["close"]), abs(today["low"] - previous["close"])) for previous, today in zip(prices, prices[1:])]
    atr = math.fsum(value / 14 for value in ranges[-14:])
    if atr <= 0:
        return {"status": "insufficient_data", "reason": "波动指标无效，无法给出价格参考"}
    parameters = settings
    support = min(row["low"] for row in prices[-20:]); resistance = max(row["high"] for row in prices[-20:])
    atr_stop = reference - parameters["atr_multiple"] * atr
    structural_stop = support - .25 * atr
    # Only include nearby support. A remote historical low must not make a
    # stop excessively wide; an above-price support must not become a stop.
    stop = min(atr_stop, structural_stop) if 0 < reference - structural_stop <= 3 * atr else atr_stop
    if stop <= 0 or stop >= reference:
        return {"status": "insufficient_data", "reason": "波动过大或支撑结构无效，无法建立正止损价"}
    risk = reference - stop
    target1 = reference + parameters["target_r"] * risk
    target2 = reference + (parameters["target_r"] + 1) * risk
    distance_percent = risk / reference * 100
    cap = min(parameters["position_cap_percent"], parameters["risk_budget_percent"] / distance_percent * 100)
    if not all(math.isfinite(value) for value in (atr,stop,risk,target1,target2,distance_percent,cap)) or not stop < reference < target1 < target2:
        return {"status": "insufficient_data", "reason": "价格计算超出可验证数值精度，无法建立有序保护价"}
    return {"status": "ok", "history_timing_status": timing["status"], "history_lag_calendar_days": timing.get("history_lag_calendar_days"), "history_lag_trading_days": timing.get("history_lag_trading_days"), "history_calendar": timing.get("history_calendar"), "quote_as_of": item.get("quote_as_of"), "currency": currency, "side": "long", "reference_price": reference, "history_as_of": latest[-1].get("date"), "atr14": atr, "support20": support, "resistance20": resistance, "stop_loss": stop, "take_profit_1": target1, "take_profit_2": target2, "risk_reward_1": parameters["target_r"], "risk_reward_2": parameters["target_r"] + 1, "stop_distance_percent": distance_percent, "position_cap_percent": cap, "risk_budget_percent": parameters["risk_budget_percent"], "atr_multiple": parameters["atr_multiple"], "resistance_before_target": reference < resistance < target1, "trailing_distance": parameters["atr_multiple"] * atr, "basis": ["ATR14为最近14日真实波幅的简单平均", "止损结合ATR距离与20日支撑下方0.25ATR缓冲", "第一/第二目标按参数R与参数R+1计算，需同时观察历史阻力", "仓位上限=min(模式上限,组合风险预算/止损距离)，金额需使用同一币种"], "limitations": ["以当前参考价构建情景，不是成交价或个人持仓成本", "默认保护参数尚未通过跨市场稳健性验证，回测候选参数不自动应用于此参考", "跳空、停牌或流动性不足可能使实际损失超过止损预算", "移动止损参考应随新的高点更新，不能降低已有保护价"]}
