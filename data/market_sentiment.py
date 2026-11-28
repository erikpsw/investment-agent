"""Quantitative 3-market (CN, HK, US) broad-market sentiment engine.

Scores each market on a unified 0-100 temperature scale:
- 0 = Extreme Fear / Bottom Opportunity (higher recommended equity allocation)
- 100 = Extreme Greed / Overheated Risk (lower recommended equity allocation)

All scoring and resonance evaluation functions are pure and deterministic so
they can be unit-tested offline; live fetchers run concurrently with timeouts,
TTL caching, and atomic snapshot fallback (`storage/market/sentiment.json`).
"""
from __future__ import annotations

import json
import math
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "storage" / "market" / "sentiment.json"
CN_MARKET_SNAPSHOT_PATH = ROOT / "storage" / "market" / "latest.json"

CACHE_SECONDS = 900  # 15 minutes
_cache_lock = threading.Lock()
_cache: dict[str, Any] = {"expires_at": 0.0, "payload": None}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Pure math & regime helpers
# ---------------------------------------------------------------------------

def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def clamp_score(value: float) -> float:
    """Clamp any numeric score into [0.0, 100.0] rounded to 1 decimal."""
    parsed = _finite(value)
    if parsed is None:
        return 50.0
    return round(max(0.0, min(100.0, parsed)), 1)


def piecewise_score(value: float, anchors: Sequence[tuple[float, float]]) -> float:
    """Linearly interpolate a metric value across sorted (x, score) anchors."""
    if not anchors:
        return 50.0
    ordered = sorted(anchors, key=lambda pair: pair[0])
    if value <= ordered[0][0]:
        return clamp_score(ordered[0][1])
    if value >= ordered[-1][0]:
        return clamp_score(ordered[-1][1])
    for (x0, y0), (x1, y1) in zip(ordered, ordered[1:]):
        if x0 <= value <= x1:
            if x1 == x0:
                return clamp_score((y0 + y1) / 2.0)
            ratio = (value - x0) / (x1 - x0)
            return clamp_score(y0 + ratio * (y1 - y0))
    return clamp_score(ordered[-1][1])


def percentile_rank(series: Sequence[float], value: float) -> float:
    """Return [0.0, 100.0] percentile rank of `value` inside `series`."""
    valid = [v for item in series if (v := _finite(item)) is not None]
    target = _finite(value)
    if not valid or target is None:
        return 50.0
    if len(valid) == 1:
        return 50.0
    below = sum(1 for item in valid if item < target)
    equal = sum(1 for item in valid if item == target)
    pct = ((below + 0.5 * max(0, equal - 1)) / (len(valid) - 1)) * 100.0
    return clamp_score(pct)


def compute_rsi(closes: Sequence[float], period: int = 14) -> float | None:
    """Compute Wilder-smoothed 14-day RSI from chronological closes."""
    series = [v for item in closes if (v := _finite(item)) is not None]
    if len(series) < period + 1:
        return None
    deltas = [curr - prev for prev, curr in zip(series, series[1:])]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0 and avg_gain == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def compute_realized_vol(closes: Sequence[float], window: int = 20) -> float | None:
    """Annualized log-return volatility (%) over trailing `window` sessions."""
    series = [v for item in closes if (v := _finite(item)) is not None and v > 0]
    if len(series) < window + 1:
        return None
    tail = series[-(window + 1):]
    returns = [math.log(curr / prev) for prev, curr in zip(tail, tail[1:])]
    if len(returns) < 2:
        return None
    vol = statistics.stdev(returns) * math.sqrt(252.0) * 100.0
    return round(vol, 2)


REGIME_ORDER = ("extreme_fear", "fear", "neutral", "greed", "extreme_greed")
REGIME_THRESHOLDS = (20.0, 35.0, 65.0, 80.0)


def compute_ema(values: Sequence[float], span: int = 5) -> list[float]:
    """Compute standard exponential moving average over finite values."""
    clean = [v for item in values if (v := _finite(item)) is not None]
    if not clean:
        return []
    alpha = 2.0 / (max(1, span) + 1.0)
    out = [clean[0]]
    for val in clean[1:]:
        out.append(alpha * val + (1.0 - alpha) * out[-1])
    return [round(v, 2) for v in out]


def apply_hysteresis_regime(score: float, prev_regime: str | None, buffer: float = 3.0) -> str:
    """Apply deadband hysteresis around 20/35/65/80 boundaries to prevent regime whipsaw."""
    s = clamp_score(score)
    if prev_regime not in REGIME_ORDER:
        return classify_sentiment_regime(s)["regime"]
    idx = REGIME_ORDER.index(prev_regime)
    while idx < len(REGIME_THRESHOLDS) and s >= REGIME_THRESHOLDS[idx] + buffer:
        idx += 1
    while idx > 0 and s <= REGIME_THRESHOLDS[idx - 1] - buffer:
        idx -= 1
    return REGIME_ORDER[idx]


def detect_right_turn(
    scores: Sequence[float],
    closes: Sequence[float],
    vol_series: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Detect right-side stabilization after a recent fear trough (reduces falling-knife risk)."""
    clean_scores = [v for item in scores if (v := _finite(item)) is not None]
    clean_closes = [v for item in closes if (v := _finite(item)) is not None and v > 0]
    if len(clean_scores) < 6:
        return {"confirmed": False, "confirmations": []}

    recent_15 = clean_scores[-15:]
    curr_score = clean_scores[-1]
    if min(recent_15) > 30.0 or curr_score > 45.0:
        return {"confirmed": False, "confirmations": []}

    confirmations: list[str] = []
    recent_10_min = min(clean_scores[-10:])
    rebound = curr_score - recent_10_min
    if rebound >= 4.0 and curr_score > clean_scores[-2]:
        confirmations.append(f"情绪分自近10日低点回升 +{rebound:.1f} 分")

    if vol_series:
        clean_vol = [v for item in vol_series if (v := _finite(item)) is not None and v > 0]
        if len(clean_vol) >= 10:
            v_curr = clean_vol[-1]
            v_hi_10 = max(clean_vol[-10:])
            v_ma5 = sum(clean_vol[-5:]) / 5.0
            if v_hi_10 >= v_curr * 1.05 and v_curr < v_ma5:
                confirmations.append("波动/恐慌指标自近10日高位回落至5日均线下方")

    if len(clean_closes) >= 10:
        c_curr = clean_closes[-1]
        ma10 = sum(clean_closes[-10:]) / 10.0
        lo10 = min(clean_closes[-10:])
        if c_curr > ma10 or (lo10 > 0 and (c_curr / lo10 - 1.0) >= 0.025):
            confirmations.append("基准指数短线止跌（站上10日均线或自低点反弹超2.5%）")

    return {
        "confirmed": len(confirmations) >= 2,
        "confirmations": confirmations,
    }


def classify_sentiment_regime(
    score: float,
    market: str | None = None,
    trend_bull: bool | None = None,
) -> dict[str, Any]:
    """Map 0-100 sentiment score to regime label and position-sizing guidance."""
    s = clamp_score(score)
    if str(market or "").upper() == "US":
        is_bull = True if trend_bull is None else bool(trend_bull)
        if is_bull:
            if s < 20.0:
                return {
                    "regime": "extreme_fear",
                    "label": "极度恐慌",
                    "position_min": 95,
                    "position_max": 100,
                    "position_range": "95% - 100%",
                    "action": "牛市恐慌黄金坑，积极分批加满权益仓位",
                }
            if s < 35.0:
                return {
                    "regime": "fear",
                    "label": "恐慌偏冷",
                    "position_min": 90,
                    "position_max": 100,
                    "position_range": "90% - 100%",
                    "action": "牛市回调区，逢跌加仓宽基",
                }
            if s < 65.0:
                return {
                    "regime": "neutral",
                    "label": "中性震荡",
                    "position_min": 80,
                    "position_max": 90,
                    "position_range": "80% - 90%",
                    "action": "位于MA200上方，稳拿核心高仓位顺势持有",
                }
            if s < 80.0:
                return {
                    "regime": "greed",
                    "label": "乐观偏热",
                    "position_min": 75,
                    "position_max": 85,
                    "position_range": "75% - 85%",
                    "action": "情绪偏热但趋势完好，暂不轻易大幅减仓",
                }
            return {
                "regime": "extreme_greed",
                "label": "极度贪婪",
                "position_min": 60,
                "position_max": 75,
                "position_range": "60% - 75%",
                "action": "极度贪婪区，适度兑现部分浮盈、保留底仓",
            }
        # US Bear / Breakdown regime (S&P 500 < MA200)
        if s < 20.0:
            return {
                "regime": "extreme_fear",
                "label": "极度恐慌",
                "position_min": 75,
                "position_max": 90,
                "position_range": "75% - 90%",
                "action": "熊市极度恐慌区，左侧分批建仓",
            }
        if s < 35.0:
            return {
                "regime": "fear",
                "label": "恐慌偏冷",
                "position_min": 55,
                "position_max": 70,
                "position_range": "55% - 70%",
                "action": "跌破MA200偏弱，控制左侧加仓节奏",
            }
        if s < 65.0:
            return {
                "regime": "neutral",
                "label": "中性震荡",
                "position_min": 40,
                "position_max": 55,
                "position_range": "40% - 55%",
                "action": "位于MA200下方，防守均衡仓位为主",
            }
        if s < 80.0:
            return {
                "regime": "greed",
                "label": "乐观偏热",
                "position_min": 30,
                "position_max": 45,
                "position_range": "30% - 45%",
                "action": "熊市反弹偏热，逢高减仓防守",
            }
        return {
            "regime": "extreme_greed",
            "label": "极度贪婪",
            "position_min": 20,
            "position_max": 35,
            "position_range": "20% - 35%",
            "action": "熊市极端亢奋，右侧降仓保留现金",
        }

    if s < 20.0:
        return {
            "regime": "extreme_fear",
            "label": "极度恐慌",
            "position_min": 75,
            "position_max": 90,
            "position_range": "75% - 90%",
            "action": "左侧分批建仓，逐步提高权益仓位",
        }
    if s < 35.0:
        return {
            "regime": "fear",
            "label": "恐慌偏冷",
            "position_min": 60,
            "position_max": 75,
            "position_range": "60% - 75%",
            "action": "逢跌定投或分批加仓，保留机动资金",
        }
    if s < 65.0:
        return {
            "regime": "neutral",
            "label": "中性震荡",
            "position_min": 45,
            "position_max": 60,
            "position_range": "45% - 60%",
            "action": "维持均衡仓位，侧重行业与个股结构",
        }
    if s < 80.0:
        return {
            "regime": "greed",
            "label": "乐观偏热",
            "position_min": 30,
            "position_max": 45,
            "position_range": "30% - 45%",
            "action": "控制追高节奏，逢高分批兑现利润",
        }
    return {
        "regime": "extreme_greed",
        "label": "极度贪婪",
        "position_min": 15,
        "position_max": 30,
        "position_range": "15% - 30%",
        "action": "右侧降仓防守，提高现金或债券占比",
    }


def _weighted_score(items: Sequence[tuple[float | None, float]]) -> float:
    """Compute weighted average over available (non-None) factor scores."""
    valid = [(float(score), float(weight)) for score, weight in items if score is not None and weight > 0]
    if not valid:
        return 50.0
    total_w = sum(w for _, w in valid)
    return clamp_score(sum(s * w for s, w in valid) / total_w)


def _evaluate_resonance(
    score: float,
    bottom_triggers: list[str],
    top_triggers: list[str],
    right_turn: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build two-stage bottom (left_bottom / right_turn) and top resonance summary."""
    if right_turn and right_turn.get("confirmed"):
        confs = list(right_turn.get("confirmations") or [])
        return {
            "signal": "right_turn",
            "stage": "right_turn",
            "label": f"右侧拐点确认（{len(confs)} 项止跌共振）",
            "trigger_count": len(confs),
            "triggers": confs,
        }
    if (score <= 32.0 and len(bottom_triggers) >= 2) or (score <= 20.0 and len(bottom_triggers) >= 1):
        return {
            "signal": "bottom",
            "stage": "left_bottom",
            "label": f"左侧冰点共振（已触发 {len(bottom_triggers)} 项）",
            "trigger_count": len(bottom_triggers),
            "triggers": bottom_triggers,
        }
    if (score >= 68.0 and len(top_triggers) >= 2) or (score >= 80.0 and len(top_triggers) >= 1):
        return {
            "signal": "top",
            "stage": "top",
            "label": f"过热预警（已触发 {len(top_triggers)} 项）",
            "trigger_count": len(top_triggers),
            "triggers": top_triggers,
        }
    if bottom_triggers:
        return {
            "signal": "watch_bottom",
            "stage": "watch",
            "label": f"底部观察（{len(bottom_triggers)} 项指标偏冷，综合温度尚未进入恐慌区）",
            "trigger_count": len(bottom_triggers),
            "triggers": bottom_triggers,
        }
    if top_triggers:
        return {
            "signal": "watch_top",
            "stage": "watch",
            "label": f"偏热观察（{len(top_triggers)} 项指标偏热，综合温度尚未进入过热区）",
            "trigger_count": len(top_triggers),
            "triggers": top_triggers,
        }
    return {
        "signal": "none",
        "stage": "none",
        "label": "暂无极端共振信号",
        "trigger_count": 0,
        "triggers": [],
    }


def _ma_deviation(closes: Sequence[float], window: int) -> tuple[float | None, float | None]:
    series = [v for item in closes if (v := _finite(item)) is not None]
    if not series:
        return None, None
    latest = series[-1]
    effective = min(window, len(series))
    if effective < 20:
        return None, None
    ma = sum(series[-effective:]) / effective
    if ma <= 0:
        return None, None
    return round((latest / ma - 1.0) * 100.0, 2), round(ma, 2)


def _compute_deltas(history: Sequence[dict[str, Any]], current_score: float) -> tuple[float | None, float | None]:
    if not history:
        return None, None
    prev_1d = _finite(history[-2]["score"]) if len(history) >= 2 else None
    prev_1w = _finite(history[-6]["score"]) if len(history) >= 6 else _finite(history[0]["score"])
    delta_1d = round(current_score - prev_1d, 1) if prev_1d is not None else None
    delta_1w = round(current_score - prev_1w, 1) if prev_1w is not None else None
    return delta_1d, delta_1w


def _format_cn_turnover(amount_yuan: float) -> str:
    if amount_yuan >= 1e12:
        return f"{amount_yuan / 1e12:.2f} 万亿"
    if amount_yuan >= 1e8:
        return f"{amount_yuan / 1e8:.0f} 亿"
    return f"{amount_yuan:.0f}"


def _format_hk_turnover(amount_hkd: float) -> str:
    if amount_hkd >= 1e8:
        return f"{amount_hkd / 1e8:.0f} 亿港元"
    return f"{amount_hkd:.0f} 港元"


# ---------------------------------------------------------------------------
# Pure per-market scoring engines
# ---------------------------------------------------------------------------

def score_cn_market(payload: dict[str, Any], *, include_history: bool = True) -> dict[str, Any]:
    """Score CN A-share sentiment (0-100) from fetched or test dict payload."""
    hs300_bars: list[dict[str, Any]] = list(payload.get("hs300_bars") or [])
    sh_sz_amounts: dict[str, float] = dict(payload.get("sh_sz_amounts") or {})
    bond_10y_by_date: dict[str, float] = dict(payload.get("cn10y_by_date") or {})
    qvix_bars: list[dict[str, Any]] = list(payload.get("qvix_bars") or [])

    pe_hs300 = _finite(payload.get("hs300_pe"))
    dividend_yield = _finite(payload.get("hs300_dividend_yield"))
    cn10y = _finite(payload.get("cn10y_yield"))
    advance_ratio = _finite(payload.get("advance_ratio"))
    up_count = payload.get("up_count")
    down_count = payload.get("down_count")
    pb_below1_pct = _finite(payload.get("pb_below1_pct"))
    breadth_source = payload.get("breadth_source") or "沪深实时涨跌家数"

    dates = [str(bar["date"]) for bar in hs300_bars if _finite(bar.get("close")) is not None]
    closes = [float(bar["close"]) for bar in hs300_bars if _finite(bar.get("close")) is not None]
    latest_close = closes[-1] if closes else _finite(payload.get("benchmark_price"))
    prev_close = closes[-2] if len(closes) >= 2 else _finite(payload.get("benchmark_prev_close"))
    bench_chg = (
        round((latest_close / prev_close - 1.0) * 100.0, 2)
        if latest_close is not None and prev_close and prev_close > 0
        else _finite(payload.get("benchmark_change_percent"))
    )

    factors: list[dict[str, Any]] = []
    weighted_inputs: list[tuple[float | None, float]] = []
    bottom_triggers: list[str] = []
    top_triggers: list[str] = []

    # 1. Equity Risk Premium (ERP) - weight 0.40
    erp: float | None = None
    erp_score: float | None = None
    if pe_hs300 and pe_hs300 > 0 and cn10y is not None:
        erp = round((100.0 / pe_hs300) - cn10y, 2)
        erp_score = piecewise_score(erp, [(2.5, 95), (3.8, 75), (5.0, 50), (6.0, 25), (7.2, 5)])
        detail_parts = [f"沪深300 PE {pe_hs300:.2f}", f"10Y国债 {cn10y:.2f}%"]
        if dividend_yield is not None:
            detail_parts.append(f"股息率 {dividend_yield:.2f}%")
        factors.append({
            "key": "erp",
            "name": "股债性价比 (ERP)",
            "weight": 0.45,
            "score": erp_score,
            "value": f"{erp:.2f}%",
            "detail": " · ".join(detail_parts),
        })
        weighted_inputs.append((erp_score, 0.45))
        if erp >= 5.8:
            bottom_triggers.append(f"股债性价比 ERP 达 {erp:.2f}%，进入历史高性价比底部区间")
        elif erp <= 3.5:
            top_triggers.append(f"股债性价比 ERP 回落至 {erp:.2f}%，权益相对吸引力偏低")

    # 2. Trend & Momentum (MA120 deviation + RSI14) - weight 0.15
    ma120_dev, ma120_val = _ma_deviation(closes, 120)
    rsi14 = compute_rsi(closes, 14)
    ma20_val = sum(closes[-20:]) / 20.0 if len(closes) >= 20 else None
    is_weak_tape = (ma20_val is not None and latest_close is not None and latest_close < ma20_val) or (
        ma120_dev is not None and ma120_dev < 0.0
    )
    trend_score: float | None = None
    if ma120_dev is not None or rsi14 is not None:
        sub_parts: list[tuple[float | None, float]] = []
        if ma120_dev is not None:
            dev_score = piecewise_score(ma120_dev, [(-15, 5), (-6, 25), (0, 50), (8, 75), (20, 95)])
            sub_parts.append((dev_score, 0.60))
        if rsi14 is not None:
            rsi_score = piecewise_score(rsi14, [(25, 5), (38, 25), (50, 50), (65, 75), (78, 95)])
            sub_parts.append((rsi_score, 0.40))
        trend_score = _weighted_score(sub_parts)
        val_text = f"{ma120_dev:+.2f}%" if ma120_dev is not None else f"RSI {rsi14:.1f}"
        detail_bits = []
        if ma120_dev is not None and ma120_val is not None:
            detail_bits.append(f"偏离MA120({ma120_val:.0f}) {ma120_dev:+.2f}%")
        if rsi14 is not None:
            detail_bits.append(f"14日RSI {rsi14:.1f}")
        factors.append({
            "key": "trend",
            "name": "指数趋势与动量",
            "weight": 0.15,
            "score": trend_score,
            "value": val_text,
            "detail": " · ".join(detail_bits),
        })
        weighted_inputs.append((trend_score, 0.15))
        if (ma120_dev is not None and ma120_dev <= -5.0) or (rsi14 is not None and rsi14 <= 35.0):
            bottom_triggers.append(
                f"沪深300处于弱势超卖区（偏离MA120 {ma120_dev:+.1f}% / RSI {rsi14:.1f}）"
                if ma120_dev is not None and rsi14 is not None
                else "沪深300处于技术面超卖区间"
            )
        elif (ma120_dev is not None and ma120_dev >= 15.0) or (rsi14 is not None and rsi14 >= 72.0):
            top_triggers.append("沪深300偏离均线过高或 RSI 进入超买区")

    # 3. Turnover temperature - weight 0.25
    turnover_series: list[tuple[str, float]] = []
    for d in dates:
        amt = _finite(sh_sz_amounts.get(d))
        if amt is not None and amt > 0:
            turnover_series.append((d, amt))
    turnover_pct: float | None = None
    turnover_score: float | None = None
    if len(turnover_series) >= 10:
        vals = [amt for _, amt in turnover_series]
        ma5_series = [
            sum(vals[max(0, i - 4):i + 1]) / len(vals[max(0, i - 4):i + 1])
            for i in range(len(vals))
        ]
        latest_amt = vals[-1]
        latest_ma5 = ma5_series[-1]
        window_250 = ma5_series[-250:]
        turnover_pct = percentile_rank(window_250, latest_ma5)
        turnover_score = clamp_score(turnover_pct)
        factors.append({
            "key": "turnover",
            "name": "两市成交额温度",
            "weight": 0.25,
            "score": turnover_score,
            "value": _format_cn_turnover(latest_amt),
            "detail": f"5日均额 {_format_cn_turnover(latest_ma5)} · 近一年 {turnover_pct:.0f}% 分位",
        })
        weighted_inputs.append((turnover_score, 0.25))
        if turnover_pct <= 20.0:
            bottom_triggers.append(f"两市成交额处于近一年 {turnover_pct:.0f}% 极低分位（地量特征）")
        elif turnover_pct >= 85.0:
            top_triggers.append(f"两市成交额处于近一年 {turnover_pct:.0f}% 高分位（情绪偏拥挤）")

    # 4. Directional Volatility panic (50ETF QVIX with fallback to 20d realized vol) - weight 0.10
    vol_score: float | None = None
    qvix_val: float | None = None
    vol_pct: float | None = None
    use_qvix = False
    valid_qvix = [
        (str(item["date"]), float(item["close"]))
        for item in qvix_bars
        if _finite(item.get("close")) is not None and float(item["close"]) > 0
    ]
    if valid_qvix and dates:
        last_qvix_date = valid_qvix[-1][0]
        last_idx_date = dates[-1]
        try:
            gap_days = abs(
                (datetime.strptime(last_idx_date[:10], "%Y-%m-%d") - datetime.strptime(last_qvix_date[:10], "%Y-%m-%d")).days
            )
            use_qvix = gap_days <= 20
        except ValueError:
            use_qvix = False

    if use_qvix:
        qvix_val = valid_qvix[-1][1]
        qvix_series = [v for _, v in valid_qvix[-250:]]
        vol_pct = percentile_rank(qvix_series, qvix_val)
        if is_weak_tape or vol_pct <= 50.0:
            inv_pct = clamp_score(100.0 - vol_pct)
            abs_score = piecewise_score(qvix_val, [(12, 85), (18, 55), (24, 30), (32, 10)])
            vol_score = clamp_score(0.5 * inv_pct + 0.5 * abs_score)
            vol_dir_note = "弱势区间计为恐慌压力" if is_weak_tape else "低波偏自满"
        else:
            vol_score = clamp_score(max(50.0, min(85.0, 50.0 + 0.35 * (vol_pct - 50.0))))
            vol_dir_note = "均线之上高波偏多头躁动"
        factors.append({
            "key": "volatility",
            "name": "方向性期权波动 (QVIX)",
            "weight": 0.05,
            "score": vol_score,
            "value": f"{qvix_val:.2f}",
            "detail": f"50ETF QVIX 近一年 {vol_pct:.0f}% 分位（{vol_dir_note}，至 {valid_qvix[-1][0]}）",
        })
        weighted_inputs.append((vol_score, 0.05))
    else:
        rv_series = []
        for idx in range(20, len(closes)):
            rv = compute_realized_vol(closes[:idx + 1], 20)
            if rv is not None:
                rv_series.append(rv)
        if rv_series:
            latest_rv = rv_series[-1]
            vol_pct = percentile_rank(rv_series[-250:], latest_rv)
            if is_weak_tape or vol_pct <= 50.0:
                inv_pct = clamp_score(100.0 - vol_pct)
                abs_score = piecewise_score(latest_rv, [(12, 85), (18, 55), (24, 30), (32, 10)])
                vol_score = clamp_score(0.5 * inv_pct + 0.5 * abs_score)
                vol_dir_note = "弱势区间计为恐慌压力" if is_weak_tape else "低波偏自满"
            else:
                vol_score = clamp_score(max(50.0, min(85.0, 50.0 + 0.35 * (vol_pct - 50.0))))
                vol_dir_note = "均线之上高波偏多头躁动"
            factors.append({
                "key": "volatility",
                "name": "方向性实现波动率",
                "weight": 0.05,
                "score": vol_score,
                "value": f"{latest_rv:.1f}%",
                "detail": f"沪深300 20日年化波动率 · 近一年 {vol_pct:.0f}% 分位（{vol_dir_note}）",
            })
            weighted_inputs.append((vol_score, 0.05))

    if is_weak_tape and ((qvix_val is not None and qvix_val >= 24.0) or (vol_pct is not None and vol_pct >= 80.0)):
        bottom_triggers.append("弱势状态下波动率飙升至恐慌高位，抛压集中释放")

    # 5. Breadth & PB<1 ratio - weight 0.10
    if advance_ratio is not None or pb_below1_pct is not None:
        sub_breadth: list[tuple[float | None, float]] = []
        detail_pieces = []
        value_display = ""
        if advance_ratio is not None:
            adv_score = piecewise_score(advance_ratio, [(15, 5), (35, 28), (50, 50), (68, 75), (85, 95)])
            sub_breadth.append((adv_score, 0.65))
            value_display = f"上涨比 {advance_ratio:.1f}%"
            if up_count is not None and down_count is not None:
                detail_pieces.append(f"{breadth_source}: 涨 {up_count} / 跌 {down_count}")
            else:
                detail_pieces.append(f"{breadth_source}: {advance_ratio:.1f}%")
        if pb_below1_pct is not None:
            pb_score = piecewise_score(pb_below1_pct, [(3, 85), (6, 60), (10, 30), (15, 10)])
            sub_breadth.append((pb_score, 0.35))
            if not value_display:
                value_display = f"破净率 {pb_below1_pct:.1f}%"
            detail_pieces.append(f"破净股占比 {pb_below1_pct:.1f}%")
        breadth_score = _weighted_score(sub_breadth)
        factors.append({
            "key": "breadth",
            "name": "市场宽度与破净率",
            "weight": 0.10,
            "score": breadth_score,
            "value": value_display,
            "detail": " · ".join(detail_pieces),
        })
        weighted_inputs.append((breadth_score, 0.10))
        if advance_ratio is not None and advance_ratio <= 25.0:
            bottom_triggers.append(f"全市场上涨家数占比仅 {advance_ratio:.1f}%，盘面情绪冰点")
        elif advance_ratio is not None and advance_ratio >= 80.0:
            top_triggers.append(f"全市场普涨比率达 {advance_ratio:.1f}%，短线情绪偏亢奋")
        if pb_below1_pct is not None and pb_below1_pct >= 10.0:
            bottom_triggers.append(f"全市场破净股占比达 {pb_below1_pct:.1f}%，估值出清显著")

    # Build 60-day historical score series
    history: list[dict[str, Any]] = []
    if include_history and len(closes) >= 30:
        start_idx = max(20, len(closes) - 60)
        amt_all = [(_finite(sh_sz_amounts.get(d)) or 0.0) for d in dates]
        ma5_all = [
            sum(amt_all[max(0, j - 4):j + 1]) / len(amt_all[max(0, j - 4):j + 1])
            for j in range(len(amt_all))
        ]
        rv_by_idx: dict[int, float] = {}
        rv_list: list[float] = []
        for idx in range(20, len(closes)):
            rv = compute_realized_vol(closes[:idx + 1], 20)
            if rv is not None:
                rv_by_idx[idx] = rv
                rv_list.append(rv)

        for idx in range(start_idx, len(closes)):
            d = dates[idx]
            sub_closes = closes[:idx + 1]
            hist_inputs: list[tuple[float | None, float]] = []

            # Scaled historical ERP when PE + bond yield available
            if pe_hs300 and pe_hs300 > 0 and latest_close and latest_close > 0:
                y10 = _finite(bond_10y_by_date.get(d)) or cn10y
                if y10 is not None:
                    est_pe = pe_hs300 * (closes[idx] / latest_close)
                    if est_pe > 0:
                        hist_erp = (100.0 / est_pe) - y10
                        hist_inputs.append((piecewise_score(hist_erp, [(2.5, 95), (3.8, 75), (5.0, 50), (6.0, 25), (7.2, 5)]), 0.45))

            d_dev, _ = _ma_deviation(sub_closes, 120)
            d_rsi = compute_rsi(sub_closes, 14)
            d_ma20 = sum(sub_closes[-20:]) / 20.0 if len(sub_closes) >= 20 else None
            d_weak = (d_ma20 is not None and closes[idx] < d_ma20) or (d_dev is not None and d_dev < 0.0)
            if d_dev is not None or d_rsi is not None:
                t_parts: list[tuple[float | None, float]] = []
                if d_dev is not None:
                    t_parts.append((piecewise_score(d_dev, [(-15, 5), (-6, 25), (0, 50), (8, 75), (20, 95)]), 0.60))
                if d_rsi is not None:
                    t_parts.append((piecewise_score(d_rsi, [(25, 5), (38, 25), (50, 50), (65, 75), (78, 95)]), 0.40))
                hist_inputs.append((_weighted_score(t_parts), 0.15))

            if ma5_all[idx] > 0:
                win = [v for v in ma5_all[max(0, idx - 249):idx + 1] if v > 0]
                if len(win) >= 10:
                    hist_inputs.append((percentile_rank(win, ma5_all[idx]), 0.25))

            if idx in rv_by_idx:
                rv_win = [rv_by_idx[k] for k in range(max(20, idx - 249), idx + 1) if k in rv_by_idx]
                if rv_win:
                    rv_pct = percentile_rank(rv_win, rv_by_idx[idx])
                    if d_weak or rv_pct <= 50.0:
                        inv = 100.0 - rv_pct
                        abs_v = piecewise_score(rv_by_idx[idx], [(12, 85), (18, 55), (24, 30), (32, 10)])
                        hist_inputs.append((clamp_score(0.5 * inv + 0.5 * abs_v), 0.05))
                    else:
                        hist_inputs.append((clamp_score(max(50.0, min(85.0, 50.0 + 0.35 * (rv_pct - 50.0)))), 0.05))

            if hist_inputs:
                history.append({"date": d[:10], "score": _weighted_score(hist_inputs)})

    total_score = _weighted_score(weighted_inputs)
    if history:
        history[-1]["score"] = total_score
    prior_scores = list(payload.get("recent_scores") or [])
    if not prior_scores and len(history) >= 2:
        prior_scores = [float(h["score"]) for h in history[:-1]]
    score_seq = prior_scores + [total_score]
    ema_vals = compute_ema(score_seq, span=5)
    smoothed_score = round(ema_vals[-1], 1) if ema_vals else total_score
    vol_seq = [v for _, v in valid_qvix[-20:]] if use_qvix else None
    right_turn = detect_right_turn(score_seq, closes, vol_seq)

    regime = classify_sentiment_regime(total_score, market="CN")
    resonance = _evaluate_resonance(total_score, bottom_triggers, top_triggers, right_turn=right_turn)
    delta_1d, delta_1w = _compute_deltas(history, total_score)

    return {
        "market": "CN",
        "name": "A 股",
        "benchmark": {
            "ticker": "sh000300",
            "name": "沪深300",
            "price": round(latest_close, 2) if latest_close is not None else None,
            "change_percent": bench_chg,
        },
        "score": total_score,
        "smoothed_score": smoothed_score,
        "trend_filter": None,
        **regime,
        "delta_1d": delta_1d,
        "delta_1w": delta_1w,
        "resonance": resonance,
        "factors": factors,
        "sub_metrics": [],
        "history": history[-60:],
        "as_of": dates[-1][:10] if dates else payload.get("as_of"),
        "source": payload.get("source") or "东方财富 + AKShare 中证指数",
        "stale": bool(payload.get("stale", False)),
    }


def score_hk_market(payload: dict[str, Any], *, include_history: bool = True) -> dict[str, Any]:
    """Score HK sentiment (0-100) from fetched or test dict payload."""
    hsi_bars: list[dict[str, Any]] = list(payload.get("hsi_bars") or [])
    vhsi_bars: list[dict[str, Any]] = list(payload.get("vhsi_bars") or [])
    hsahp_bars: list[dict[str, Any]] = list(payload.get("hsahp_bars") or [])
    southbound_bars: list[dict[str, Any]] = list(payload.get("southbound_bars") or [])

    dates = [str(bar["date"]) for bar in hsi_bars if _finite(bar.get("close")) is not None]
    closes = [float(bar["close"]) for bar in hsi_bars if _finite(bar.get("close")) is not None]
    amounts = [_finite(bar.get("amount")) for bar in hsi_bars if _finite(bar.get("close")) is not None]

    latest_close = closes[-1] if closes else _finite(payload.get("benchmark_price"))
    prev_close = closes[-2] if len(closes) >= 2 else _finite(payload.get("benchmark_prev_close"))
    bench_chg = (
        round((latest_close / prev_close - 1.0) * 100.0, 2)
        if latest_close is not None and prev_close and prev_close > 0
        else _finite(payload.get("benchmark_change_percent"))
    )

    factors: list[dict[str, Any]] = []
    weighted_inputs: list[tuple[float | None, float]] = []
    bottom_triggers: list[str] = []
    top_triggers: list[str] = []

    vhsi_by_date = {
        str(b["date"])[:10]: float(b["close"])
        for b in vhsi_bars
        if _finite(b.get("close")) is not None and float(b["close"]) > 0
    }
    hsahp_by_date = {
        str(b["date"])[:10]: float(b["close"])
        for b in hsahp_bars
        if _finite(b.get("close")) is not None and float(b["close"]) > 0
    }

    # Precompute HK tape weakness (below MA20 or MA120) so VHSI spikes during rallies aren't misread as panic
    ma120_dev, ma120_val = _ma_deviation(closes, 120)
    rsi14 = compute_rsi(closes, 14)
    ma20_val = sum(closes[-20:]) / 20.0 if len(closes) >= 20 else None
    is_weak_tape = (ma20_val is not None and latest_close is not None and latest_close < ma20_val) or (
        ma120_dev is not None and ma120_dev < 0.0
    )

    # 1. Directional VHSI - weight 0.20
    vhsi_vals = [float(b["close"]) for b in vhsi_bars if _finite(b.get("close")) is not None and float(b["close"]) > 0]
    if vhsi_vals:
        latest_vhsi = vhsi_vals[-1]
        vhsi_pct = percentile_rank(vhsi_vals[-250:], latest_vhsi)
        if is_weak_tape or vhsi_pct <= 50.0:
            inv_pct = clamp_score(100.0 - vhsi_pct)
            abs_score = piecewise_score(latest_vhsi, [(14, 90), (19, 65), (24, 42), (30, 20), (38, 5)])
            vhsi_score = clamp_score(0.5 * inv_pct + 0.5 * abs_score)
            vhsi_note = "弱势区间计为恐慌压力" if is_weak_tape else "低波偏自满"
        else:
            vhsi_score = clamp_score(max(50.0, min(85.0, 50.0 + 0.30 * (vhsi_pct - 50.0))))
            vhsi_note = "均线之上高波偏多头活跃"
        factors.append({
            "key": "vhsi",
            "name": "方向性恒生波幅 (VHSI)",
            "weight": 0.20,
            "score": vhsi_score,
            "value": f"{latest_vhsi:.2f}",
            "detail": f"港股恐慌指数 · 近一年 {vhsi_pct:.0f}% 分位（{vhsi_note}）",
        })
        weighted_inputs.append((vhsi_score, 0.20))
        if is_weak_tape and (latest_vhsi >= 28.0 or vhsi_pct >= 80.0):
            bottom_triggers.append(f"弱势下恒生波幅 VHSI 升至 {latest_vhsi:.2f}（近一年 {vhsi_pct:.0f}% 高分位）")
        elif latest_vhsi <= 16.0:
            top_triggers.append(f"VHSI 降至 {latest_vhsi:.2f} 极低水平，警惕波动放大")

    # 2. AH Premium Index (HSAHP) - weight 0.25
    hsahp_vals = [float(b["close"]) for b in hsahp_bars if _finite(b.get("close")) is not None and float(b["close"]) > 0]
    if hsahp_vals:
        latest_ah = hsahp_vals[-1]
        ah_pct = percentile_rank(hsahp_vals[-250:], latest_ah)
        inv_pct = clamp_score(100.0 - ah_pct)
        abs_score = piecewise_score(latest_ah, [(118, 90), (128, 68), (136, 48), (144, 24), (152, 8)])
        ah_score = clamp_score(0.5 * inv_pct + 0.5 * abs_score)
        factors.append({
            "key": "ah_premium",
            "name": "恒生 AH 股溢价指数",
            "weight": 0.25,
            "score": ah_score,
            "value": f"{latest_ah:.2f}",
            "detail": f"A股相对H股溢价 {latest_ah - 100:.1f}% · 近一年 {ah_pct:.0f}% 分位",
        })
        weighted_inputs.append((ah_score, 0.25))
        if latest_ah >= 142.0 or ah_pct >= 80.0:
            bottom_triggers.append(f"AH 股溢价指数达 {latest_ah:.2f}，H 股相对折价显著")
        elif latest_ah <= 122.0:
            top_triggers.append(f"AH 股溢价指数收窄至 {latest_ah:.2f}，H 股折价优势减弱")

    # 3. HSI Trend & Momentum - weight 0.15
    if ma120_dev is not None or rsi14 is not None:
        t_parts: list[tuple[float | None, float]] = []
        if ma120_dev is not None:
            t_parts.append((piecewise_score(ma120_dev, [(-18, 5), (-7, 25), (0, 50), (9, 75), (22, 95)]), 0.60))
        if rsi14 is not None:
            t_parts.append((piecewise_score(rsi14, [(25, 5), (38, 25), (50, 50), (65, 75), (78, 95)]), 0.40))
        trend_score = _weighted_score(t_parts)
        detail_bits = []
        if ma120_dev is not None and ma120_val is not None:
            detail_bits.append(f"偏离MA120({ma120_val:.0f}) {ma120_dev:+.2f}%")
        if rsi14 is not None:
            detail_bits.append(f"14日RSI {rsi14:.1f}")
        factors.append({
            "key": "trend",
            "name": "恒指趋势与动量",
            "weight": 0.15,
            "score": trend_score,
            "value": f"{ma120_dev:+.2f}%" if ma120_dev is not None else f"RSI {rsi14:.1f}",
            "detail": " · ".join(detail_bits),
        })
        weighted_inputs.append((trend_score, 0.15))
        if (ma120_dev is not None and ma120_dev <= -5.0) or (rsi14 is not None and rsi14 <= 35.0):
            bottom_triggers.append(
                f"恒生指数处于弱势超卖区（偏离MA120 {ma120_dev:+.1f}% / RSI {rsi14:.1f}）"
                if ma120_dev is not None and rsi14 is not None
                else "恒生指数处于技术超卖区"
            )
        elif (ma120_dev is not None and ma120_dev >= 15.0) or (rsi14 is not None and rsi14 >= 72.0):
            top_triggers.append("恒生指数偏离均线过高或 RSI 超买")

    # 4. HK Liquidity Activity (offshore market: higher liquidity = institutional return, low liquidity = dry-up risk) - weight 0.10
    valid_amts = [a for a in amounts if a is not None and a > 0]
    if len(valid_amts) >= 10:
        ma5_amts = [
            sum(valid_amts[max(0, i - 4):i + 1]) / len(valid_amts[max(0, i - 4):i + 1])
            for i in range(len(valid_amts))
        ]
        latest_amt = valid_amts[-1]
        latest_ma5 = ma5_amts[-1]
        t_pct = percentile_rank(ma5_amts[-250:], latest_ma5)
        liq_score = piecewise_score(t_pct, [(10, 72), (35, 58), (65, 42), (90, 25)])
        factors.append({
            "key": "turnover",
            "name": "港股流动性活跃度",
            "weight": 0.10,
            "score": liq_score,
            "value": _format_hk_turnover(latest_amt),
            "detail": f"5日均额 {_format_hk_turnover(latest_ma5)} · 近一年 {t_pct:.0f}% 分位（放量偏资金回流支撑，缩量易阴跌）",
        })
        weighted_inputs.append((liq_score, 0.10))

    # 5. Southbound 20d Net Inflow - weight 0.30
    sb_vals = [_finite(b.get("net_yi")) for b in southbound_bars]
    sb_clean = [v for v in sb_vals if v is not None]
    if sb_clean:
        sb_20d = round(sum(sb_clean[-20:]), 1)
        sb_latest = round(sb_clean[-1], 1)
        sb_score = piecewise_score(sb_20d, [(-300, 82), (-50, 62), (100, 48), (350, 26), (700, 10)])
        factors.append({
            "key": "southbound",
            "name": "南向资金 20 日净流入",
            "weight": 0.30,
            "score": sb_score,
            "value": f"{sb_20d:+.0f} 亿",
            "detail": f"最近交易日 {sb_latest:+.1f} 亿人民币 · 逆势持续净流入偏支撑",
        })
        weighted_inputs.append((sb_score, 0.30))
        if sb_20d >= 300.0:
            bottom_triggers.append(f"南向资金近 20 日逆势净流入 {sb_20d:.0f} 亿元")
        elif sb_20d <= -150.0:
            top_triggers.append(f"南向资金近 20 日持续净流出 {sb_20d:.0f} 亿元")

    # 60-day history
    history: list[dict[str, Any]] = []
    if include_history and len(closes) >= 30:
        start_idx = max(20, len(closes) - 60)
        amt_filled = [(a if a is not None and a > 0 else 0.0) for a in amounts]
        ma5_all = [
            sum(amt_filled[max(0, j - 4):j + 1]) / len(amt_filled[max(0, j - 4):j + 1])
            for j in range(len(amt_filled))
        ]
        sb_by_date = {
            str(b["date"])[:10]: float(b["net_yi"])
            for b in southbound_bars
            if _finite(b.get("net_yi")) is not None
        }
        sb_sorted_dates = sorted(sb_by_date.keys())
        for idx in range(start_idx, len(closes)):
            d = dates[idx][:10]
            sub_closes = closes[:idx + 1]
            hist_inputs: list[tuple[float | None, float]] = []

            d_dev, _ = _ma_deviation(sub_closes, 120)
            d_rsi = compute_rsi(sub_closes, 14)
            d_ma20 = sum(sub_closes[-20:]) / 20.0 if len(sub_closes) >= 20 else None
            d_weak = (d_ma20 is not None and closes[idx] < d_ma20) or (d_dev is not None and d_dev < 0.0)

            if d in vhsi_by_date:
                v_win = [vhsi_by_date[dates[k][:10]] for k in range(max(0, idx - 249), idx + 1) if dates[k][:10] in vhsi_by_date]
                v_val = vhsi_by_date[d]
                v_pct = percentile_rank(v_win, v_val) if len(v_win) >= 5 else 50.0
                if d_weak or v_pct <= 50.0:
                    inv = 100.0 - v_pct
                    abs_v = piecewise_score(v_val, [(14, 90), (19, 65), (24, 42), (30, 20), (38, 5)])
                    hist_inputs.append((clamp_score(0.5 * inv + 0.5 * abs_v), 0.20))
                else:
                    hist_inputs.append((clamp_score(max(50.0, min(85.0, 50.0 + 0.30 * (v_pct - 50.0)))), 0.20))

            if d in hsahp_by_date:
                a_win = [hsahp_by_date[dates[k][:10]] for k in range(max(0, idx - 249), idx + 1) if dates[k][:10] in hsahp_by_date]
                a_val = hsahp_by_date[d]
                inv = 100.0 - percentile_rank(a_win, a_val) if len(a_win) >= 5 else 50.0
                abs_a = piecewise_score(a_val, [(118, 90), (128, 68), (136, 48), (144, 24), (152, 8)])
                hist_inputs.append((clamp_score(0.5 * inv + 0.5 * abs_a), 0.25))

            if d_dev is not None or d_rsi is not None:
                t_parts: list[tuple[float | None, float]] = []
                if d_dev is not None:
                    t_parts.append((piecewise_score(d_dev, [(-18, 5), (-7, 25), (0, 50), (9, 75), (22, 95)]), 0.60))
                if d_rsi is not None:
                    t_parts.append((piecewise_score(d_rsi, [(25, 5), (38, 25), (50, 50), (65, 75), (78, 95)]), 0.40))
                hist_inputs.append((_weighted_score(t_parts), 0.15))

            if ma5_all[idx] > 0:
                win = [v for v in ma5_all[max(0, idx - 249):idx + 1] if v > 0]
                if len(win) >= 10:
                    t_pct = percentile_rank(win, ma5_all[idx])
                    hist_inputs.append((piecewise_score(t_pct, [(10, 72), (35, 58), (65, 42), (90, 25)]), 0.10))

            sb_upto = [sb_by_date[sd] for sd in sb_sorted_dates if sd <= d][-20:]
            if sb_upto:
                hist_inputs.append((piecewise_score(sum(sb_upto), [(-300, 82), (-50, 62), (100, 48), (350, 26), (700, 10)]), 0.30))

            if hist_inputs:
                history.append({"date": d, "score": _weighted_score(hist_inputs)})

    total_score = _weighted_score(weighted_inputs)
    if history:
        history[-1]["score"] = total_score
    prior_scores = list(payload.get("recent_scores") or [])
    if not prior_scores and len(history) >= 2:
        prior_scores = [float(h["score"]) for h in history[:-1]]
    score_seq = prior_scores + [total_score]
    ema_vals = compute_ema(score_seq, span=5)
    smoothed_score = round(ema_vals[-1], 1) if ema_vals else total_score
    right_turn = detect_right_turn(score_seq, closes, vhsi_vals[-20:] if vhsi_vals else None)

    regime = classify_sentiment_regime(total_score, market="HK")
    resonance = _evaluate_resonance(total_score, bottom_triggers, top_triggers, right_turn=right_turn)
    delta_1d, delta_1w = _compute_deltas(history, total_score)

    return {
        "market": "HK",
        "name": "港股",
        "benchmark": {
            "ticker": "^HSI",
            "name": "恒生指数",
            "price": round(latest_close, 2) if latest_close is not None else None,
            "change_percent": bench_chg,
        },
        "score": total_score,
        "smoothed_score": smoothed_score,
        "trend_filter": None,
        **regime,
        "delta_1d": delta_1d,
        "delta_1w": delta_1w,
        "resonance": resonance,
        "factors": factors,
        "sub_metrics": [],
        "history": history[-60:],
        "as_of": dates[-1][:10] if dates else payload.get("as_of"),
        "source": payload.get("source") or "东方财富 (VHSI / AH溢价 / 港股通)",
        "stale": bool(payload.get("stale", False)),
    }


_CNN_SUB_LABELS: list[tuple[str, str]] = [
    ("market_momentum_sp500", "标普500动量"),
    ("stock_price_strength", "52周新高新低"),
    ("stock_price_breadth", "成交量广度"),
    ("put_call_options", "期权 Put/Call"),
    ("market_volatility_vix", "VIX 波动率"),
    ("junk_bond_demand", "垃圾债需求"),
    ("safe_haven_demand", "股债避险需求"),
]

_CNN_RATING_ZH = {
    "extreme fear": "极度恐慌",
    "fear": "恐慌",
    "neutral": "中性",
    "greed": "贪婪",
    "extreme greed": "极度贪婪",
}


def score_us_market(payload: dict[str, Any], *, include_history: bool = True) -> dict[str, Any]:
    """Score US sentiment (0-100) from fetched or test dict payload."""
    cnn_data: dict[str, Any] = dict(payload.get("cnn") or {})
    spx_bars: list[dict[str, Any]] = list(payload.get("spx_bars") or [])
    vix_bars: list[dict[str, Any]] = list(payload.get("vix_bars") or [])
    vix3m_bars: list[dict[str, Any]] = list(payload.get("vix3m_bars") or [])
    hyg_bars: list[dict[str, Any]] = list(payload.get("hyg_bars") or [])
    ief_bars: list[dict[str, Any]] = list(payload.get("ief_bars") or [])

    spx_dates = [str(b["date"]) for b in spx_bars if _finite(b.get("close")) is not None]
    spx_closes = [float(b["close"]) for b in spx_bars if _finite(b.get("close")) is not None]
    latest_close = spx_closes[-1] if spx_closes else _finite(payload.get("benchmark_price"))
    prev_close = spx_closes[-2] if len(spx_closes) >= 2 else _finite(payload.get("benchmark_prev_close"))
    bench_chg = (
        round((latest_close / prev_close - 1.0) * 100.0, 2)
        if latest_close is not None and prev_close and prev_close > 0
        else _finite(payload.get("benchmark_change_percent"))
    )

    factors: list[dict[str, Any]] = []
    weighted_inputs: list[tuple[float | None, float]] = []
    bottom_triggers: list[str] = []
    top_triggers: list[str] = []
    sub_metrics: list[dict[str, Any]] = []

    # 1. CNN Fear & Greed Index - weight 0.45
    fg = cnn_data.get("fear_and_greed") or {}
    cnn_score = _finite(fg.get("score"))
    if cnn_score is not None:
        cnn_score = clamp_score(cnn_score)
        rating_raw = str(fg.get("rating") or "").lower()
        rating_zh = _CNN_RATING_ZH.get(rating_raw, rating_raw or "未知")
        factors.append({
            "key": "cnn_fear_greed",
            "name": "CNN 恐慌与贪婪指数",
            "weight": 0.45,
            "score": cnn_score,
            "value": f"{cnn_score:.1f}",
            "detail": f"官方评级: {rating_zh} · 7 项华尔街情绪子指标合成",
        })
        weighted_inputs.append((cnn_score, 0.45))
        if cnn_score <= 25.0:
            bottom_triggers.append(f"CNN 恐慌与贪婪指数跌至 {cnn_score:.1f}（极度恐慌区）")
        elif cnn_score >= 75.0:
            top_triggers.append(f"CNN 恐慌与贪婪指数升至 {cnn_score:.1f}（极度贪婪区）")

        for key, zh_name in _CNN_SUB_LABELS:
            item = cnn_data.get(key)
            if isinstance(item, dict) and _finite(item.get("score")) is not None:
                sub_score = clamp_score(float(item["score"]))
                sub_rating = str(item.get("rating") or "").lower()
                last_pts = item.get("data") or []
                raw_y = _finite(last_pts[-1].get("y")) if last_pts and isinstance(last_pts[-1], dict) else None
                sub_metrics.append({
                    "key": key,
                    "name": zh_name,
                    "score": sub_score,
                    "rating": _CNN_RATING_ZH.get(sub_rating, sub_rating),
                    "value": round(raw_y, 2) if raw_y is not None else None,
                })

    # 2. VIX & Term Structure (VIX / VIX3M) - weight 0.25
    vix_by_date = {
        str(b["date"])[:10]: float(b["close"])
        for b in vix_bars
        if _finite(b.get("close")) is not None and float(b["close"]) > 0
    }
    vix3m_by_date = {
        str(b["date"])[:10]: float(b["close"])
        for b in vix3m_bars
        if _finite(b.get("close")) is not None and float(b["close"]) > 0
    }
    latest_vix = _finite(vix_bars[-1].get("close")) if vix_bars else None
    latest_vix3m = _finite(vix3m_bars[-1].get("close")) if vix3m_bars else None
    vix_ratio: float | None = None
    if latest_vix is not None:
        vix_abs_score = piecewise_score(latest_vix, [(12, 92), (16, 65), (21, 42), (28, 18), (36, 5)])
        if latest_vix3m and latest_vix3m > 0:
            vix_ratio = round(latest_vix / latest_vix3m, 3)
            ratio_score = piecewise_score(vix_ratio, [(0.78, 92), (0.88, 62), (0.95, 38), (1.00, 18), (1.08, 5)])
            vix_score = clamp_score(0.60 * ratio_score + 0.40 * vix_abs_score)
            val_text = f"比值 {vix_ratio:.2f}"
            detail_text = f"VIX {latest_vix:.2f} / VIX3M {latest_vix3m:.2f}（>=1.00 为期限倒挂）"
        else:
            vix_score = vix_abs_score
            val_text = f"VIX {latest_vix:.2f}"
            detail_text = "CBOE 标普500隐含波动率"

        factors.append({
            "key": "vix_term",
            "name": "VIX 期限结构与恐慌",
            "weight": 0.30,
            "score": vix_score,
            "value": val_text,
            "detail": detail_text,
        })
        weighted_inputs.append((vix_score, 0.30))
        if vix_ratio is not None and vix_ratio >= 0.98:
            bottom_triggers.append(f"VIX/VIX3M 比值达 {vix_ratio:.2f}（期限结构逼近或进入倒挂）")
        if latest_vix >= 25.0:
            bottom_triggers.append(f"VIX 恐慌指数飙升至 {latest_vix:.2f}")
        elif latest_vix <= 14.0 and (vix_ratio is None or vix_ratio <= 0.85):
            top_triggers.append(f"VIX 处于 {latest_vix:.2f} 极度自满低位")

    # 3. S&P 500 Trend & Momentum (MA125 + RSI14) - weight 0.15
    ma125_dev, ma125_val = _ma_deviation(spx_closes, 125)
    rsi14 = compute_rsi(spx_closes, 14)
    if ma125_dev is not None or rsi14 is not None:
        t_parts: list[tuple[float | None, float]] = []
        if ma125_dev is not None:
            t_parts.append((piecewise_score(ma125_dev, [(-12, 5), (-4, 25), (2, 50), (9, 75), (18, 95)]), 0.60))
        if rsi14 is not None:
            t_parts.append((piecewise_score(rsi14, [(25, 5), (38, 25), (50, 50), (65, 75), (78, 95)]), 0.40))
        trend_score = _weighted_score(t_parts)
        detail_bits = []
        if ma125_dev is not None and ma125_val is not None:
            detail_bits.append(f"偏离MA125({ma125_val:.0f}) {ma125_dev:+.2f}%")
        if rsi14 is not None:
            detail_bits.append(f"14日RSI {rsi14:.1f}")
        factors.append({
            "key": "trend",
            "name": "标普500 趋势与动量",
            "weight": 0.15,
            "score": trend_score,
            "value": f"{ma125_dev:+.2f}%" if ma125_dev is not None else f"RSI {rsi14:.1f}",
            "detail": " · ".join(detail_bits),
        })
        weighted_inputs.append((trend_score, 0.15))
        if (ma125_dev is not None and ma125_dev <= -2.0) or (rsi14 is not None and rsi14 <= 35.0):
            bottom_triggers.append("标普500回落至 MA125 下方或 RSI 超卖")
        elif (ma125_dev is not None and ma125_dev >= 12.0) or (rsi14 is not None and rsi14 >= 72.0):
            top_triggers.append("标普500偏离 MA125 过大或 RSI 超买")

    # 4. Credit Risk Appetite (HYG vs IEF 20d spread) - weight 0.10
    hyg_closes = [float(b["close"]) for b in hyg_bars if _finite(b.get("close")) is not None and float(b["close"]) > 0]
    ief_closes = [float(b["close"]) for b in ief_bars if _finite(b.get("close")) is not None and float(b["close"]) > 0]
    if len(hyg_closes) >= 21 and len(ief_closes) >= 21:
        hyg_ret = (hyg_closes[-1] / hyg_closes[-21] - 1.0) * 100.0
        ief_ret = (ief_closes[-1] / ief_closes[-21] - 1.0) * 100.0
        spread = round(hyg_ret - ief_ret, 2)
        credit_score = piecewise_score(spread, [(-4.0, 10), (-1.5, 30), (0.5, 55), (2.5, 80), (5.0, 95)])
        factors.append({
            "key": "credit_spread",
            "name": "高收益债风险偏好 (HYG/IEF)",
            "weight": 0.10,
            "score": credit_score,
            "value": f"{spread:+.2f}%",
            "detail": f"20日 HYG({hyg_ret:+.2f}%) - IEF({ief_ret:+.2f}%)",
        })
        weighted_inputs.append((credit_score, 0.10))

    # 60-day history (prefer CNN official historical curve, fallback to Yahoo composite)
    history: list[dict[str, Any]] = []
    cnn_hist_raw = (cnn_data.get("fear_and_greed_historical") or {}).get("data") or []
    if include_history and cnn_hist_raw:
        by_day: dict[str, float] = {}
        for pt in cnn_hist_raw:
            if not isinstance(pt, dict):
                continue
            ts = _finite(pt.get("x"))
            val = _finite(pt.get("y"))
            if ts is None or val is None:
                continue
            day = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            by_day[day] = clamp_score(val)
        sorted_days = sorted(by_day.keys())[-60:]
        for d in sorted_days:
            # Blend CNN historical curve with VIX/SPX on matching dates when available
            hist_inputs: list[tuple[float | None, float]] = [(by_day[d], 0.65)]
            if d in vix_by_date:
                v = vix_by_date[d]
                v_abs = piecewise_score(v, [(12, 92), (16, 65), (21, 42), (28, 18), (36, 5)])
                if d in vix3m_by_date and vix3m_by_date[d] > 0:
                    r_sc = piecewise_score(v / vix3m_by_date[d], [(0.78, 92), (0.88, 62), (0.95, 38), (1.00, 18), (1.08, 5)])
                    hist_inputs.append((clamp_score(0.6 * r_sc + 0.4 * v_abs), 0.35))
                else:
                    hist_inputs.append((v_abs, 0.35))
            history.append({"date": d, "score": _weighted_score(hist_inputs)})
    elif include_history and len(spx_closes) >= 30:
        start_idx = max(20, len(spx_closes) - 60)
        for idx in range(start_idx, len(spx_closes)):
            d = spx_dates[idx][:10]
            hist_inputs = []
            if d in vix_by_date:
                v = vix_by_date[d]
                v_abs = piecewise_score(v, [(12, 92), (16, 65), (21, 42), (28, 18), (36, 5)])
                if d in vix3m_by_date and vix3m_by_date[d] > 0:
                    r_sc = piecewise_score(v / vix3m_by_date[d], [(0.78, 92), (0.88, 62), (0.95, 38), (1.00, 18), (1.08, 5)])
                    hist_inputs.append((clamp_score(0.6 * r_sc + 0.4 * v_abs), 0.60))
                else:
                    hist_inputs.append((v_abs, 0.60))
            d_dev, _ = _ma_deviation(spx_closes[:idx + 1], 125)
            d_rsi = compute_rsi(spx_closes[:idx + 1], 14)
            if d_dev is not None or d_rsi is not None:
                t_parts: list[tuple[float | None, float]] = []
                if d_dev is not None:
                    t_parts.append((piecewise_score(d_dev, [(-12, 5), (-4, 25), (2, 50), (9, 75), (18, 95)]), 0.60))
                if d_rsi is not None:
                    t_parts.append((piecewise_score(d_rsi, [(25, 5), (38, 25), (50, 50), (65, 75), (78, 95)]), 0.40))
                hist_inputs.append((_weighted_score(t_parts), 0.40))
            if hist_inputs:
                history.append({"date": d, "score": _weighted_score(hist_inputs)})

    total_score = _weighted_score(weighted_inputs)
    if history:
        history[-1]["score"] = total_score

    ma200_val: float | None = None
    trend_bull: bool | None = None
    trend_filter: dict[str, Any] | None = None
    if len(spx_closes) >= 200 and latest_close is not None:
        ma200_val = round(sum(spx_closes[-200:]) / 200.0, 2)
        trend_bull = latest_close >= ma200_val
        trend_filter = {
            "regime": "bull" if trend_bull else "bear",
            "label": f"牛市滤网（标普500 ≥ MA200 {ma200_val:.0f}）" if trend_bull else f"防守滤网（标普500 < MA200 {ma200_val:.0f}）",
            "ma200": ma200_val,
            "above_ma200": trend_bull,
        }

    prior_scores = list(payload.get("recent_scores") or [])
    if not prior_scores and len(history) >= 2:
        prior_scores = [float(h["score"]) for h in history[:-1]]
    score_seq = prior_scores + [total_score]
    ema_vals = compute_ema(score_seq, span=5)
    smoothed_score = round(ema_vals[-1], 1) if ema_vals else total_score
    vix_seq = [float(b["close"]) for b in vix_bars[-20:] if _finite(b.get("close")) is not None]
    right_turn = detect_right_turn(score_seq, spx_closes, vix_seq if vix_seq else None)

    regime = classify_sentiment_regime(total_score, market="US", trend_bull=trend_bull)
    resonance = _evaluate_resonance(total_score, bottom_triggers, top_triggers, right_turn=right_turn)
    delta_1d, delta_1w = _compute_deltas(history, total_score)

    as_of_date = spx_dates[-1][:10] if spx_dates else None
    if not as_of_date and fg.get("timestamp"):
        as_of_date = str(fg["timestamp"])[:10]

    return {
        "market": "US",
        "name": "美股",
        "benchmark": {
            "ticker": "^GSPC",
            "name": "标普500",
            "price": round(latest_close, 2) if latest_close is not None else None,
            "change_percent": bench_chg,
        },
        "score": total_score,
        "smoothed_score": smoothed_score,
        "trend_filter": trend_filter,
        **regime,
        "delta_1d": delta_1d,
        "delta_1w": delta_1w,
        "resonance": resonance,
        "factors": factors,
        "sub_metrics": sub_metrics,
        "history": history[-60:],
        "as_of": as_of_date or payload.get("as_of"),
        "source": payload.get("source") or "CNN Fear & Greed + CBOE VIX + Yahoo Finance",
        "stale": bool(payload.get("stale", False)),
    }


# ---------------------------------------------------------------------------
# Live network fetchers (isolated, timeout-bounded)
# ---------------------------------------------------------------------------

def _fetch_eastmoney_kline(secid: str, limit: int = 500) -> list[dict[str, Any]]:
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3",
        "fields2": "f51,f53,f56,f57",
        "klt": "101",
        "fqt": "0",
        "end": "20500101",
        "lmt": str(limit),
    }
    resp = requests.get(url, params=params, headers=BROWSER_HEADERS, timeout=7)
    resp.raise_for_status()
    klines = ((resp.json().get("data") or {}).get("klines")) or []
    bars: list[dict[str, Any]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 2:
            continue
        close = _finite(parts[1])
        if close is None:
            continue
        bars.append({
            "date": parts[0][:10],
            "close": close,
            "volume": _finite(parts[2]) if len(parts) > 2 else None,
            "amount": _finite(parts[3]) if len(parts) > 3 else None,
        })
    return bars


def _fetch_eastmoney_bond_10y() -> tuple[float | None, dict[str, float]]:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPTA_WEB_TREASURYYIELD",
        "columns": "SOLAR_DATE,EMM00166466,EMG00001310",
        "pageSize": "500",
        "sortColumns": "SOLAR_DATE",
        "sortTypes": "-1",
    }
    resp = requests.get(url, params=params, headers=BROWSER_HEADERS, timeout=7)
    resp.raise_for_status()
    rows = ((resp.json().get("result") or {}).get("data")) or []
    by_date: dict[str, float] = {}
    latest: float | None = None
    for row in rows:
        day = str(row.get("SOLAR_DATE") or "")[:10]
        val = _finite(row.get("EMM00166466"))
        if day and val is not None:
            if latest is None:
                latest = val
            by_date[day] = val
    return latest, by_date


def _fetch_cn_live_breadth() -> tuple[float | None, int | None, int | None, float | None, str]:
    up_total: int | None = None
    down_total: int | None = None
    adv_ratio: float | None = None
    breadth_source = "沪深实时涨跌家数"
    try:
        resp = requests.get(
            "https://push2.eastmoney.com/api/qt/ulist.np/get",
            params={"fltt": "2", "secids": "1.000001,0.399001", "fields": "f12,f104,f105,f106"},
            headers=BROWSER_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        diff = ((resp.json().get("data") or {}).get("diff")) or []
        ups = sum(int(item.get("f104") or 0) for item in diff)
        downs = sum(int(item.get("f105") or 0) for item in diff)
        if ups + downs > 0:
            up_total = ups
            down_total = downs
            adv_ratio = round(ups / (ups + downs) * 100.0, 2)
    except Exception:
        pass

    pb_below1_pct: float | None = None
    if CN_MARKET_SNAPSHOT_PATH.exists():
        try:
            snap = json.loads(CN_MARKET_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            snap_dt_raw = str(snap.get("generated_at") or "")
            is_recent = False
            if snap_dt_raw:
                try:
                    snap_dt = datetime.fromisoformat(snap_dt_raw.replace("Z", "+00:00"))
                    age_days = abs((datetime.now(timezone.utc) - snap_dt.astimezone(timezone.utc)).total_seconds()) / 86400.0
                    is_recent = age_days <= 14.0
                except ValueError:
                    is_recent = False
            rows = snap.get("rows") or []
            if is_recent and rows:
                pbs = [_finite(r.get("pb_ratio")) for r in rows]
                valid_pbs = [p for p in pbs if p is not None and p > 0]
                if valid_pbs:
                    pb_below1_pct = round(sum(1 for p in valid_pbs if p < 1.0) / len(valid_pbs) * 100.0, 2)
                if adv_ratio is None:
                    chgs = [_finite(r.get("today_change_percent")) for r in rows]
                    valid_chgs = [c for c in chgs if c is not None]
                    if valid_chgs:
                        up_total = sum(1 for c in valid_chgs if c > 0)
                        down_total = sum(1 for c in valid_chgs if c < 0)
                        if up_total + down_total > 0:
                            adv_ratio = round(up_total / (up_total + down_total) * 100.0, 2)
                            breadth_source = "A股快照涨跌比"
        except Exception:
            pass

    return adv_ratio, up_total, down_total, pb_below1_pct, breadth_source


def _fetch_cn_payload() -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=5) as ex:
        f_hs300 = ex.submit(_fetch_eastmoney_kline, "1.000300", 500)
        f_sh = ex.submit(_fetch_eastmoney_kline, "1.000001", 500)
        f_sz = ex.submit(_fetch_eastmoney_kline, "0.399001", 500)
        f_bond = ex.submit(_fetch_eastmoney_bond_10y)
        f_breadth = ex.submit(_fetch_cn_live_breadth)

        def _fetch_ak_pe() -> tuple[float | None, float | None]:
            try:
                import akshare as ak
                df = ak.stock_zh_index_value_csindex(symbol="000300")
                if df is not None and not df.empty:
                    df = df.sort_values("日期", ascending=True)
                    row = df.iloc[-1]
                    return _finite(row.get("市盈率1")), _finite(row.get("股息率1"))
            except Exception:
                pass
            return None, None

        def _fetch_ak_qvix() -> list[dict[str, Any]]:
            try:
                import akshare as ak
                df = ak.index_option_50etf_qvix()
                if df is not None and not df.empty and "close" in df.columns:
                    df = df.dropna(subset=["close"]).tail(260)
                    return [
                        {"date": str(r["date"])[:10], "close": float(r["close"])}
                        for _, r in df.iterrows()
                        if _finite(r.get("close")) is not None
                    ]
            except Exception:
                pass
            return []

        f_pe = ex.submit(_fetch_ak_pe)
        f_qvix = ex.submit(_fetch_ak_qvix)

        hs300_bars = f_hs300.result()
        sh_bars = f_sh.result()
        sz_bars = f_sz.result()
        cn10y, cn10y_by_date = f_bond.result()
        adv_ratio, up_count, down_count, pb_below1_pct, breadth_source = f_breadth.result()
        hs300_pe, hs300_div = f_pe.result()
        qvix_bars = f_qvix.result()

    sh_sz_amounts: dict[str, float] = {}
    for bar in sh_bars:
        if bar.get("amount") is not None:
            sh_sz_amounts[bar["date"]] = sh_sz_amounts.get(bar["date"], 0.0) + float(bar["amount"])
    for bar in sz_bars:
        if bar.get("amount") is not None:
            sh_sz_amounts[bar["date"]] = sh_sz_amounts.get(bar["date"], 0.0) + float(bar["amount"])

    return {
        "hs300_bars": hs300_bars,
        "sh_sz_amounts": sh_sz_amounts,
        "hs300_pe": hs300_pe,
        "hs300_dividend_yield": hs300_div,
        "cn10y_yield": cn10y,
        "cn10y_by_date": cn10y_by_date,
        "qvix_bars": qvix_bars,
        "advance_ratio": adv_ratio,
        "up_count": up_count,
        "down_count": down_count,
        "pb_below1_pct": pb_below1_pct,
        "breadth_source": breadth_source,
    }


def _fetch_southbound_history() -> list[dict[str, Any]]:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    totals_by_date: dict[str, float] = {}
    for mtype in ("002", "004"):
        resp = requests.get(
            url,
            params={
                "reportName": "RPT_MUTUAL_DEAL_HISTORY",
                "columns": "TRADE_DATE,NET_DEAL_AMT",
                "filter": f'(MUTUAL_TYPE="{mtype}")',
                "pageSize": "90",
                "sortColumns": "TRADE_DATE",
                "sortTypes": "-1",
            },
            headers=BROWSER_HEADERS,
            timeout=7,
        )
        resp.raise_for_status()
        rows = ((resp.json().get("result") or {}).get("data")) or []
        for row in rows:
            day = str(row.get("TRADE_DATE") or "")[:10]
            amt_m = _finite(row.get("NET_DEAL_AMT"))
            if day and amt_m is not None:
                totals_by_date[day] = totals_by_date.get(day, 0.0) + (amt_m / 100.0)
    return [{"date": d, "net_yi": round(totals_by_date[d], 2)} for d in sorted(totals_by_date.keys())]


def _fetch_hk_payload() -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_hsi = ex.submit(_fetch_eastmoney_kline, "100.HSI", 500)
        f_vhsi = ex.submit(_fetch_eastmoney_kline, "124.VHSI", 500)
        f_hsahp = ex.submit(_fetch_eastmoney_kline, "100.HSAHP", 500)
        f_sb = ex.submit(_fetch_southbound_history)

        hsi_bars = f_hsi.result()
        vhsi_bars = f_vhsi.result()
        hsahp_bars = f_hsahp.result()
        try:
            southbound_bars = f_sb.result()
        except Exception:
            southbound_bars = []

    return {
        "hsi_bars": hsi_bars,
        "vhsi_bars": vhsi_bars,
        "hsahp_bars": hsahp_bars,
        "southbound_bars": southbound_bars,
    }


def _fetch_yahoo_chart_bars(symbol: str, range_str: str = "2y") -> list[dict[str, Any]]:
    encoded = quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
    resp = requests.get(
        url,
        params={"range": range_str, "interval": "1d"},
        headers=BROWSER_HEADERS,
        timeout=7,
    )
    resp.raise_for_status()
    result = ((resp.json().get("chart") or {}).get("result") or [None])[0] or {}
    timestamps = result.get("timestamp") or []
    quote_obj = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote_obj.get("close") or []
    bars: list[dict[str, Any]] = []
    for ts, close in zip(timestamps, closes):
        val = _finite(close)
        if ts is None or val is None:
            continue
        day = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        bars.append({"date": day, "close": val})
    return bars


def _fetch_cnn_fear_greed() -> dict[str, Any]:
    headers = {**BROWSER_HEADERS, "Referer": "https://www.cnn.com/"}
    resp = requests.get(
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        headers=headers,
        timeout=7,
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_us_payload() -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=6) as ex:
        f_cnn = ex.submit(_fetch_cnn_fear_greed)
        f_spx = ex.submit(_fetch_yahoo_chart_bars, "^GSPC", "2y")
        f_vix = ex.submit(_fetch_yahoo_chart_bars, "^VIX", "2y")
        f_vix3m = ex.submit(_fetch_yahoo_chart_bars, "^VIX3M", "2y")
        f_hyg = ex.submit(_fetch_yahoo_chart_bars, "HYG", "6mo")
        f_ief = ex.submit(_fetch_yahoo_chart_bars, "IEF", "6mo")

        def _safe(fut):
            try:
                return fut.result()
            except Exception:
                return None

        cnn = _safe(f_cnn) or {}
        spx_bars = _safe(f_spx) or []
        vix_bars = _safe(f_vix) or []
        vix3m_bars = _safe(f_vix3m) or []
        hyg_bars = _safe(f_hyg) or []
        ief_bars = _safe(f_ief) or []

    return {
        "cnn": cnn,
        "spx_bars": spx_bars,
        "vix_bars": vix_bars,
        "vix3m_bars": vix3m_bars,
        "hyg_bars": hyg_bars,
        "ief_bars": ief_bars,
    }


# ---------------------------------------------------------------------------
# Snapshot persistence, caching, and public entrypoint
# ---------------------------------------------------------------------------

def _read_snapshot() -> dict[str, Any] | None:
    if not SNAPSHOT_PATH.exists():
        return None
    try:
        data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("markets"), list):
            return data
    except Exception:
        return None
    return None


def _write_snapshot_atomic(payload: dict[str, Any]) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = SNAPSHOT_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(SNAPSHOT_PATH)


def _compute_live_sentiment() -> dict[str, Any]:
    existing_snap = _read_snapshot()
    existing_by_market = {
        str(item.get("market")): item
        for item in (existing_snap or {}).get("markets", [])
        if isinstance(item, dict) and item.get("market")
    }

    def _run_market(market: str, fetcher, scorer) -> tuple[dict[str, Any] | None, bool]:
        try:
            raw = fetcher()
            scored = scorer(raw)
            if scored.get("factors"):
                return scored, True
        except Exception:
            pass
        fallback = existing_by_market.get(market)
        if fallback:
            return {**fallback, "stale": True}, False
        return None, False

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_cn = ex.submit(_run_market, "CN", _fetch_cn_payload, score_cn_market)
        f_hk = ex.submit(_run_market, "HK", _fetch_hk_payload, score_hk_market)
        f_us = ex.submit(_run_market, "US", _fetch_us_payload, score_us_market)
        cn_res, cn_live = f_cn.result()
        hk_res, hk_live = f_hk.result()
        us_res, us_live = f_us.result()

    markets = [item for item in (cn_res, hk_res, us_res) if item is not None]
    if not markets:
        raise RuntimeError("All market sentiment providers failed and no snapshot is available")

    live_count = sum(1 for ok in (cn_live, hk_live, us_live) if ok)
    generated_at = datetime.now().astimezone().isoformat()
    return {
        "generated_at": generated_at,
        "stale": live_count < 3,
        "live_markets": live_count,
        "markets": markets,
    }


def get_market_sentiment(force_refresh: bool = False) -> dict[str, Any]:
    """Return 3-market sentiment payload using TTL cache + snapshot fallback."""
    now = time.time()
    if not force_refresh:
        with _cache_lock:
            if _cache["payload"] is not None and now < _cache["expires_at"]:
                return _cache["payload"]

    try:
        result = _compute_live_sentiment()
    except Exception:
        snap = _read_snapshot()
        if not snap:
            raise
        result = {
            **snap,
            "stale": True,
            "markets": [{**m, "stale": True} for m in snap.get("markets", [])],
        }

    with _cache_lock:
        _cache["payload"] = result
        _cache["expires_at"] = now + CACHE_SECONDS
    return result


def refresh_sentiment_snapshot() -> dict[str, Any]:
    """Compute live sentiment and persist `storage/market/sentiment.json`."""
    result = _compute_live_sentiment()
    if int(result.get("live_markets") or 0) < 2:
        raise RuntimeError(f"Too few live markets succeeded ({result.get('live_markets')}); refusing to overwrite snapshot")
    snapshot_payload = {
        "generated_at": result["generated_at"],
        "stale": False,
        "markets": [{**m, "stale": False} for m in result["markets"]],
    }
    _write_snapshot_atomic(snapshot_payload)
    return snapshot_payload
