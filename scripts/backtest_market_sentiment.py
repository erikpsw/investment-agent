"""10-year point-in-time backtest for the 3-market quantitative sentiment engine.

Evaluates:
1. Regime bucket forward returns (20D / 60D / 120D / 250D) & Spearman rank IC.
2. Bottom & top resonance episodes (20D cooldown deduplication), win rates, and left-side drawdown pain.
3. T+1 dynamic position sizing (5-tier regime switching & weekly linear) vs 100% Buy & Hold and
   static equal-exposure benchmarks (after 0.05% one-way transaction costs).
4. Single-factor IC ablation to diagnose which factors carry predictive alpha.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from investment.data.market_sentiment import (  # noqa: E402
    BROWSER_HEADERS,
    _fetch_cnn_fear_greed,
    _fetch_eastmoney_kline,
    apply_hysteresis_regime,
    classify_sentiment_regime,
    score_cn_market,
    score_hk_market,
    score_us_market,
)

CACHE_DIR = ROOT / "storage" / "cache" / "sentiment_backtest"
REPORT_JSON_PATH = ROOT / "reports" / "sentiment_backtest_summary.json"
REPORT_MD_PATH = ROOT / "reports" / "sentiment_backtest_report.md"

REGIME_REP_SCORE = {
    "extreme_fear": 10.0,
    "fear": 27.5,
    "neutral": 50.0,
    "greed": 72.5,
    "extreme_greed": 90.0,
}

TIER_MIDPOINT = {
    "extreme_fear": 0.825,
    "fear": 0.675,
    "neutral": 0.525,
    "greed": 0.375,
    "extreme_greed": 0.225,
}
TIER_ORDER = ["extreme_fear", "fear", "neutral", "greed", "extreme_greed"]
TIER_LABEL = {
    "extreme_fear": "极度恐慌 (0-20)",
    "fear": "恐慌偏冷 (20-35)",
    "neutral": "中性震荡 (35-65)",
    "greed": "乐观偏热 (65-80)",
    "extreme_greed": "极度贪婪 (80-100)",
}


# ---------------------------------------------------------------------------
# Cached data loaders (~10y)
# ---------------------------------------------------------------------------

def _load_or_fetch(name: str, fetcher, refresh: bool = False) -> Any:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetcher()
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def _fetch_bond10y_10y() -> dict[str, float]:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    by_date: dict[str, float] = {}
    for page in range(1, 9):
        resp = requests.get(
            url,
            params={
                "reportName": "RPTA_WEB_TREASURYYIELD",
                "columns": "SOLAR_DATE,EMM00166466",
                "pageSize": "500",
                "pageNumber": str(page),
                "sortColumns": "SOLAR_DATE",
                "sortTypes": "-1",
            },
            headers=BROWSER_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        rows = ((resp.json().get("result") or {}).get("data")) or []
        if not rows:
            break
        for row in rows:
            day = str(row.get("SOLAR_DATE") or "")[:10]
            val = row.get("EMM00166466")
            if day and isinstance(val, (int, float)) and math.isfinite(val):
                by_date[day] = float(val)
    return dict(sorted(by_date.items()))


def _fetch_hs300_pe_lg() -> list[dict[str, Any]]:
    import akshare as ak
    df = ak.stock_index_pe_lg(symbol="沪深300")
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        day = str(row["日期"])[:10]
        pe = row.get("滚动市盈率")
        if day and pe is not None and not (isinstance(pe, float) and math.isnan(pe)):
            records.append({"date": day, "pe": float(pe)})
    records.sort(key=lambda r: r["date"])
    return records


def _fetch_qvix_all() -> list[dict[str, Any]]:
    import akshare as ak
    df = ak.index_option_50etf_qvix().dropna(subset=["close"])
    bars = []
    for _, row in df.iterrows():
        day = str(row["date"])[:10]
        val = float(row["close"])
        if math.isfinite(val) and val > 0:
            bars.append({"date": day, "close": val})
    bars.sort(key=lambda r: r["date"])
    return bars


def _fetch_southbound_10y() -> list[dict[str, Any]]:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    totals: dict[str, float] = {}
    for mtype in ("002", "004"):
        for page in range(1, 7):
            resp = requests.get(
                url,
                params={
                    "reportName": "RPT_MUTUAL_DEAL_HISTORY",
                    "columns": "TRADE_DATE,NET_DEAL_AMT",
                    "filter": f'(MUTUAL_TYPE="{mtype}")',
                    "pageSize": "500",
                    "pageNumber": str(page),
                    "sortColumns": "TRADE_DATE",
                    "sortTypes": "-1",
                },
                headers=BROWSER_HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            rows = ((resp.json().get("result") or {}).get("data")) or []
            if not rows:
                break
            for row in rows:
                day = str(row.get("TRADE_DATE") or "")[:10]
                amt = row.get("NET_DEAL_AMT")
                if day and isinstance(amt, (int, float)) and math.isfinite(amt):
                    totals[day] = totals.get(day, 0.0) + (float(amt) / 100.0)
    return [{"date": d, "net_yi": round(totals[d], 2)} for d in sorted(totals.keys())]


def _fetch_yahoo_10y(symbol: str) -> list[dict[str, Any]]:
    encoded = quote(symbol, safe="")
    resp = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}",
        params={"range": "10y", "interval": "1d"},
        headers=BROWSER_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    res = ((resp.json().get("chart") or {}).get("result") or [None])[0] or {}
    ts_list = res.get("timestamp") or []
    closes = ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    bars = []
    for ts, close in zip(ts_list, closes):
        if ts is None or close is None or not isinstance(close, (int, float)) or not math.isfinite(close):
            continue
        day = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        bars.append({"date": day, "close": float(close)})
    return bars


# ---------------------------------------------------------------------------
# Pure statistical & simulation helpers
# ---------------------------------------------------------------------------

def _rank_with_ties(values: Sequence[float]) -> list[float]:
    n = len(values)
    indexed = sorted(enumerate(values), key=lambda p: p[1])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def spearman_corr(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 20:
        return None
    rx = _rank_with_ties(xs)
    ry = _rank_with_ties(ys)
    mx = sum(rx) / len(rx)
    my = sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den_x = sum((a - mx) ** 2 for a in rx)
    den_y = sum((b - my) ** 2 for b in ry)
    den = math.sqrt(den_x * den_y)
    if den <= 0:
        return None
    return round(num / den, 4)


def _slice_bars_upto(bars: list[dict[str, Any]], dates: list[str], cutoff_date: str, max_len: int = 260) -> list[dict[str, Any]]:
    idx = bisect_right(dates, cutoff_date)
    start = max(0, idx - max_len)
    return bars[start:idx]


def _forward_stats(records: list[dict[str, Any]], closes: list[float]) -> dict[str, Any]:
    n = len(records)
    horizons = (20, 60, 120, 250)

    # Precompute forward returns & 60d max further drawdown per index t
    fwd_by_idx: dict[int, dict[str, float | None]] = {}
    for i, rec in enumerate(records):
        t = rec["idx"]
        c0 = closes[t]
        row_fwd: dict[str, float | None] = {}
        for h in horizons:
            row_fwd[f"ret_{h}"] = (closes[t + h] / c0 - 1.0) * 100.0 if t + h < len(closes) else None
        if t + 1 < len(closes):
            end_60 = min(len(closes), t + 61)
            min_60 = min(closes[t + 1:end_60])
            row_fwd["mdd_60"] = (min_60 / c0 - 1.0) * 100.0
            end_120 = min(len(closes), t + 121)
            min_120 = min(closes[t + 1:end_120])
            row_fwd["mdd_120"] = (min_120 / c0 - 1.0) * 100.0
        else:
            row_fwd["mdd_60"] = None
            row_fwd["mdd_120"] = None
        fwd_by_idx[i] = row_fwd

    # 1. Rank IC across all days
    ic: dict[str, float | None] = {}
    for h in horizons:
        pairs = [
            (records[i]["score"], fwd_by_idx[i][f"ret_{h}"])
            for i in range(n)
            if fwd_by_idx[i][f"ret_{h}"] is not None
        ]
        ic[f"ic_{h}d"] = spearman_corr([p[0] for p in pairs], [p[1] for p in pairs])  # type: ignore[arg-type]

    # 2. Regime buckets
    buckets: list[dict[str, Any]] = []
    for tier in TIER_ORDER:
        idxs = [i for i in range(n) if records[i]["regime"] == tier]
        entry: dict[str, Any] = {
            "regime": tier,
            "label": TIER_LABEL[tier],
            "days": len(idxs),
            "pct_days": round(len(idxs) / max(n, 1) * 100.0, 1),
        }
        for h in horizons:
            vals = [fwd_by_idx[i][f"ret_{h}"] for i in idxs if fwd_by_idx[i][f"ret_{h}"] is not None]
            if vals:
                clean = [float(v) for v in vals]
                entry[f"mean_{h}d"] = round(sum(clean) / len(clean), 2)
                entry[f"median_{h}d"] = round(statistics.median(clean), 2)
                entry[f"win_{h}d"] = round(sum(1 for v in clean if v > 0) / len(clean) * 100.0, 1)
            else:
                entry[f"mean_{h}d"] = None
                entry[f"median_{h}d"] = None
                entry[f"win_{h}d"] = None
        mdd60 = [float(fwd_by_idx[i]["mdd_60"]) for i in idxs if fwd_by_idx[i]["mdd_60"] is not None]
        entry["avg_mdd_60d"] = round(sum(mdd60) / len(mdd60), 2) if mdd60 else None
        buckets.append(entry)

    # 3. Resonance episodes (20-trading-day cooldown)
    def _episodes(target_signal: str) -> dict[str, Any]:
        selected: list[int] = []
        last_pos = -999
        for i in range(n):
            if records[i]["resonance_signal"] == target_signal and (i - last_pos) >= 20:
                selected.append(i)
                last_pos = i
        episodes_detail = []
        for i in selected:
            f = fwd_by_idx[i]
            episodes_detail.append({
                "date": records[i]["date"],
                "price": round(closes[records[i]["idx"]], 2),
                "score": records[i]["score"],
                "triggers": records[i]["triggers"],
                "ret_60d": round(f["ret_60"], 2) if f["ret_60"] is not None else None,
                "ret_120d": round(f["ret_120"], 2) if f["ret_120"] is not None else None,
                "ret_250d": round(f["ret_250"], 2) if f["ret_250"] is not None else None,
                "mdd_60d": round(f["mdd_60"], 2) if f["mdd_60"] is not None else None,
                "mdd_120d": round(f["mdd_120"], 2) if f["mdd_120"] is not None else None,
            })

        def _agg(key: str) -> dict[str, Any]:
            vals = [ep[key] for ep in episodes_detail if ep[key] is not None]
            if not vals:
                return {"n": 0, "mean": None, "median": None, "win_rate": None}
            return {
                "n": len(vals),
                "mean": round(sum(vals) / len(vals), 2),
                "median": round(statistics.median(vals), 2),
                "win_rate": round(sum(1 for v in vals if v > 0) / len(vals) * 100.0, 1),
            }

        mdd_key = "mdd_60d" if target_signal in ("bottom", "right_turn") else "mdd_120d"
        mdd_vals = [ep[mdd_key] for ep in episodes_detail if ep[mdd_key] is not None]
        return {
            "count": len(episodes_detail),
            "r60": _agg("ret_60d"),
            "r120": _agg("ret_120d"),
            "r250": _agg("ret_250d"),
            "avg_pain_mdd": round(sum(mdd_vals) / len(mdd_vals), 2) if mdd_vals else None,
            "worst_pain_mdd": round(min(mdd_vals), 2) if mdd_vals else None,
            "episodes": episodes_detail,
        }

    # 4. Single-factor IC ablation
    factor_keys: list[str] = []
    seen_keys: set[str] = set()
    for rec in records:
        for fk in rec["factor_scores"]:
            if fk not in seen_keys:
                seen_keys.add(fk)
                factor_keys.append(fk)

    factor_ablation = []
    for fk in factor_keys:
        pairs_60 = [
            (records[i]["factor_scores"][fk], fwd_by_idx[i]["ret_60"])
            for i in range(n)
            if fk in records[i]["factor_scores"] and fwd_by_idx[i]["ret_60"] is not None
        ]
        pairs_120 = [
            (records[i]["factor_scores"][fk], fwd_by_idx[i]["ret_120"])
            for i in range(n)
            if fk in records[i]["factor_scores"] and fwd_by_idx[i]["ret_120"] is not None
        ]
        pairs_250 = [
            (records[i]["factor_scores"][fk], fwd_by_idx[i]["ret_250"])
            for i in range(n)
            if fk in records[i]["factor_scores"] and fwd_by_idx[i]["ret_250"] is not None
        ]
        cold = [float(r) for s, r in pairs_120 if s < 25.0]  # type: ignore[arg-type]
        hot = [float(r) for s, r in pairs_120 if s > 75.0]  # type: ignore[arg-type]
        factor_ablation.append({
            "key": fk,
            "name": records[-1]["factor_names"].get(fk, fk),
            "ic_60d": spearman_corr([p[0] for p in pairs_60], [p[1] for p in pairs_60]),  # type: ignore[arg-type]
            "ic_120d": spearman_corr([p[0] for p in pairs_120], [p[1] for p in pairs_120]),  # type: ignore[arg-type]
            "ic_250d": spearman_corr([p[0] for p in pairs_250], [p[1] for p in pairs_250]),  # type: ignore[arg-type]
            "cold_120d_mean": round(sum(cold) / len(cold), 2) if cold else None,
            "cold_days": len(cold),
            "hot_120d_mean": round(sum(hot) / len(hot), 2) if hot else None,
            "hot_days": len(hot),
        })

    return {
        "ic": ic,
        "buckets": buckets,
        "bottom_episodes": _episodes("bottom"),
        "right_turn_episodes": _episodes("right_turn"),
        "top_episodes": _episodes("top"),
        "factor_ablation": factor_ablation,
    }


def _simulate_strategy(
    records: list[dict[str, Any]],
    closes: list[float],
    weights_fn,
    *,
    cash_annual_yield: float = 0.0,
    fee_one_way: float = 0.0005,
) -> dict[str, Any]:
    """T+1 close-to-close portfolio simulation."""
    nav = 1.0
    peak = 1.0
    max_dd = 0.0
    daily_rets: list[float] = []
    weights_used: list[float] = []
    turnover = 0.0
    rebalances = 0
    prev_w = float(weights_fn(0, records[0], None))
    daily_cash_ret = cash_annual_yield / 252.0

    # First day uses initial weight without entry fee distortion; each subsequent rebalance pays fee on |dw|
    for i in range(len(records) - 1):
        t = records[i]["idx"]
        t_next = records[i + 1]["idx"]
        target_w = float(weights_fn(i, records[i], prev_w))
        dw = abs(target_w - prev_w)
        cost = dw * fee_one_way
        if dw > 1e-6:
            turnover += dw
            rebalances += 1
        eq_ret = closes[t_next] / closes[t] - 1.0
        port_ret = target_w * eq_ret + (1.0 - target_w) * daily_cash_ret - cost
        nav *= (1.0 + port_ret)
        peak = max(peak, nav)
        dd = nav / peak - 1.0
        max_dd = min(max_dd, dd)
        daily_rets.append(port_ret)
        weights_used.append(target_w)
        prev_w = target_w

    years = len(daily_rets) / 252.0
    cagr = (nav ** (1.0 / years) - 1.0) * 100.0 if years > 0 else 0.0
    total_ret = (nav - 1.0) * 100.0
    vol = statistics.stdev(daily_rets) * math.sqrt(252.0) * 100.0 if len(daily_rets) >= 2 else 0.0
    mean_ann = (sum(daily_rets) / len(daily_rets)) * 252.0 * 100.0 if daily_rets else 0.0
    rf = cash_annual_yield * 100.0
    sharpe = (mean_ann - rf) / vol if vol > 0 else 0.0
    max_dd_pct = max_dd * 100.0
    calmar = cagr / abs(max_dd_pct) if max_dd_pct < 0 else 0.0

    return {
        "total_return_pct": round(total_ret, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "ann_vol_pct": round(vol, 2),
        "sharpe": round(sharpe, 2),
        "calmar": round(calmar, 2),
        "avg_exposure_pct": round(sum(weights_used) / len(weights_used) * 100.0, 1) if weights_used else 0.0,
        "rebalances": rebalances,
        "ann_turnover_pct": round(turnover / max(years, 1e-6) * 100.0, 1),
    }


def _run_simulations(
    records: list[dict[str, Any]],
    closes: list[float],
    cash_rate: float,
    market: str,
) -> dict[str, Any]:
    tier_fn = lambda _i, rec, _pw: rec["position_mid"]
    hyst_fn = lambda _i, rec, _pw: rec["hyst_position_mid"]
    if market == "US":
        linear_weekly_fn = lambda i, rec, pw: (
            max(0.40, min(1.00, 1.00 - 0.0055 * rec["score"]))
            if (i == 0 or i % 5 == 0 or pw is None)
            else pw
        )
    else:
        linear_weekly_fn = lambda i, rec, pw: (
            max(0.15, min(0.90, 0.90 - 0.0065 * rec["score"]))
            if (i == 0 or i % 5 == 0 or pw is None)
            else pw
        )

    sim_tier_0 = _simulate_strategy(records, closes, tier_fn, cash_annual_yield=0.0)
    sim_hyst_0 = _simulate_strategy(records, closes, hyst_fn, cash_annual_yield=0.0)
    avg_w = sim_hyst_0["avg_exposure_pct"] / 100.0
    static_eq_fn = lambda _i, _rec, _pw: avg_w
    bh_fn = lambda _i, _rec, _pw: 1.0

    return {
        "pure_timing_0_cash": {
            "buy_and_hold": _simulate_strategy(records, closes, bh_fn, cash_annual_yield=0.0, fee_one_way=0.0),
            "static_equal_exposure": _simulate_strategy(records, closes, static_eq_fn, cash_annual_yield=0.0, fee_one_way=0.0),
            "dynamic_5_tier": sim_tier_0,
            "dynamic_hysteresis": sim_hyst_0,
            "dynamic_linear_weekly": _simulate_strategy(records, closes, linear_weekly_fn, cash_annual_yield=0.0),
        },
        "with_cash_yield": {
            "cash_yield_pct": round(cash_rate * 100.0, 1),
            "buy_and_hold": _simulate_strategy(records, closes, bh_fn, cash_annual_yield=cash_rate, fee_one_way=0.0),
            "static_equal_exposure": _simulate_strategy(records, closes, static_eq_fn, cash_annual_yield=cash_rate, fee_one_way=0.0),
            "dynamic_5_tier": _simulate_strategy(records, closes, tier_fn, cash_annual_yield=cash_rate),
            "dynamic_hysteresis": _simulate_strategy(records, closes, hyst_fn, cash_annual_yield=cash_rate),
            "dynamic_linear_weekly": _simulate_strategy(records, closes, linear_weekly_fn, cash_annual_yield=cash_rate),
        },
    }


def _split_validation(
    records: list[dict[str, Any]],
    closes: list[float],
    cash_rate: float,
    market: str,
) -> dict[str, Any]:
    """Strict split-sample validation: pre-2021 (in-sample) vs 2021-2026 (out-of-sample)."""
    out: dict[str, Any] = {}
    splits = [
        ("pre_2021", [r for r in records if r["date"] <= "2020-12-31"]),
        ("oos_2021_2026", [r for r in records if r["date"] >= "2021-01-01"]),
    ]
    for label, sub in splits:
        if len(sub) < 100:
            continue
        fwd = _forward_stats(sub, closes)
        sims = _run_simulations(sub, closes, cash_rate, market)
        out[label] = {
            "start_date": sub[0]["date"],
            "end_date": sub[-1]["date"],
            "trading_days": len(sub),
            "ic": fwd["ic"],
            "bottom_episodes": {k: v for k, v in fwd["bottom_episodes"].items() if k != "episodes"},
            "right_turn_episodes": {k: v for k, v in fwd["right_turn_episodes"].items() if k != "episodes"},
            "simulations": sims["with_cash_yield"],
        }
    return out


# ---------------------------------------------------------------------------
# Per-market replay runners
# ---------------------------------------------------------------------------

def run_cn_backtest(refresh: bool = False) -> dict[str, Any]:
    hs300_bars = _load_or_fetch("cn_hs300", lambda: _fetch_eastmoney_kline("1.000300", 3000), refresh)
    sh_bars = _load_or_fetch("cn_sh", lambda: _fetch_eastmoney_kline("1.000001", 3000), refresh)
    sz_bars = _load_or_fetch("cn_sz", lambda: _fetch_eastmoney_kline("0.399001", 3000), refresh)
    bond_by_date = _load_or_fetch("cn_bond10y", _fetch_bond10y_10y, refresh)
    pe_records = _load_or_fetch("cn_hs300_pe", _fetch_hs300_pe_lg, refresh)
    qvix_bars = _load_or_fetch("cn_qvix", _fetch_qvix_all, refresh)

    sh_sz_amounts: dict[str, float] = {}
    for b in sh_bars:
        if b.get("amount") is not None:
            sh_sz_amounts[b["date"]] = sh_sz_amounts.get(b["date"], 0.0) + float(b["amount"])
    for b in sz_bars:
        if b.get("amount") is not None:
            sh_sz_amounts[b["date"]] = sh_sz_amounts.get(b["date"], 0.0) + float(b["amount"])

    pe_dates = [r["date"] for r in pe_records]
    qvix_dates = [b["date"] for b in qvix_bars]
    bond_dates = sorted(bond_by_date.keys())
    closes = [float(b["close"]) for b in hs300_bars]

    records: list[dict[str, Any]] = []
    recent_scores: list[float] = []
    hyst_regime: str | None = None
    parity_checked = 0
    for t in range(250, len(hs300_bars)):
        d = hs300_bars[t]["date"]
        pe_idx = bisect_right(pe_dates, d) - 1
        pe_val = pe_records[pe_idx]["pe"] if pe_idx >= 0 else None
        b_idx = bisect_right(bond_dates, d) - 1
        bond_val = bond_by_date[bond_dates[b_idx]] if b_idx >= 0 else None

        slice_hs300 = hs300_bars[max(0, t - 259):t + 1]
        slice_dates = {b["date"] for b in slice_hs300}
        slice_amounts = {k: sh_sz_amounts[k] for k in slice_dates if k in sh_sz_amounts}
        slice_qvix = _slice_bars_upto(qvix_bars, qvix_dates, d, 260)

        payload = {
            "hs300_bars": slice_hs300,
            "sh_sz_amounts": slice_amounts,
            "hs300_pe": pe_val,
            "cn10y_yield": bond_val,
            "cn10y_by_date": {},
            "qvix_bars": slice_qvix,
            "recent_scores": recent_scores[-20:],
        }
        res = score_cn_market(payload, include_history=False)

        if parity_checked < 5 and t % 450 == 250:
            full_res = score_cn_market({**payload, "hs300_bars": hs300_bars[:t + 1]}, include_history=True)
            assert res["score"] == full_res["score"], f"CN parity mismatch at {d}"
            parity_checked += 1

        recent_scores.append(res["score"])
        hyst_regime = apply_hysteresis_regime(res["smoothed_score"], hyst_regime, buffer=3.0)
        hyst_band = classify_sentiment_regime(REGIME_REP_SCORE[hyst_regime], market="CN")

        records.append({
            "idx": t,
            "date": d,
            "score": res["score"],
            "smoothed_score": res["smoothed_score"],
            "regime": res["regime"],
            "hyst_regime": hyst_regime,
            "position_mid": (res["position_min"] + res["position_max"]) / 200.0,
            "hyst_position_mid": (hyst_band["position_min"] + hyst_band["position_max"]) / 200.0,
            "resonance_signal": res["resonance"]["signal"],
            "triggers": res["resonance"]["triggers"],
            "factor_scores": {f["key"]: f["score"] for f in res["factors"]},
            "factor_names": {f["key"]: f["name"] for f in res["factors"]},
        })

    return {
        "market": "CN",
        "name": "A 股 (沪深300)",
        "start_date": records[0]["date"],
        "end_date": records[-1]["date"],
        "trading_days": len(records),
        "caliber_note": "严格前向无未来函数；10年历史含 ERP(45%)+两市成交额(25%)+趋势动量(15%)+方向性QVIX(5%)+5日EMA滞回+右侧拐点确认。",
        **_forward_stats(records, closes),
        "simulations": _run_simulations(records, closes, cash_rate=0.02, market="CN"),
        "split_validation": _split_validation(records, closes, cash_rate=0.02, market="CN"),
    }


def run_hk_backtest(refresh: bool = False) -> dict[str, Any]:
    hsi_bars = _load_or_fetch("hk_hsi", lambda: _fetch_eastmoney_kline("100.HSI", 3000), refresh)
    vhsi_bars = _load_or_fetch("hk_vhsi", lambda: _fetch_eastmoney_kline("124.VHSI", 3000), refresh)
    hsahp_bars = _load_or_fetch("hk_hsahp", lambda: _fetch_eastmoney_kline("100.HSAHP", 3000), refresh)
    sb_bars = _load_or_fetch("hk_southbound", _fetch_southbound_10y, refresh)

    vhsi_dates = [b["date"] for b in vhsi_bars]
    hsahp_dates = [b["date"] for b in hsahp_bars]
    sb_dates = [b["date"] for b in sb_bars]
    closes = [float(b["close"]) for b in hsi_bars]

    # Start once HSI has 250 bars AND HSAHP has at least 30 bars
    first_ah_date = hsahp_dates[29] if len(hsahp_dates) >= 30 else hsi_bars[250]["date"]
    start_t = max(250, next((i for i, b in enumerate(hsi_bars) if b["date"] >= first_ah_date), 250))

    records: list[dict[str, Any]] = []
    recent_scores: list[float] = []
    hyst_regime: str | None = None
    parity_checked = 0
    for t in range(start_t, len(hsi_bars)):
        d = hsi_bars[t]["date"]
        payload = {
            "hsi_bars": hsi_bars[max(0, t - 259):t + 1],
            "vhsi_bars": _slice_bars_upto(vhsi_bars, vhsi_dates, d, 260),
            "hsahp_bars": _slice_bars_upto(hsahp_bars, hsahp_dates, d, 260),
            "southbound_bars": _slice_bars_upto(sb_bars, sb_dates, d, 30),
            "recent_scores": recent_scores[-20:],
        }
        res = score_hk_market(payload, include_history=False)

        if parity_checked < 5 and t % 450 == 300:
            full_res = score_hk_market({**payload, "hsi_bars": hsi_bars[:t + 1]}, include_history=True)
            assert res["score"] == full_res["score"], f"HK parity mismatch at {d}"
            parity_checked += 1

        recent_scores.append(res["score"])
        hyst_regime = apply_hysteresis_regime(res["smoothed_score"], hyst_regime, buffer=3.0)
        hyst_band = classify_sentiment_regime(REGIME_REP_SCORE[hyst_regime], market="HK")

        records.append({
            "idx": t,
            "date": d,
            "score": res["score"],
            "smoothed_score": res["smoothed_score"],
            "regime": res["regime"],
            "hyst_regime": hyst_regime,
            "position_mid": (res["position_min"] + res["position_max"]) / 200.0,
            "hyst_position_mid": (hyst_band["position_min"] + hyst_band["position_max"]) / 200.0,
            "resonance_signal": res["resonance"]["signal"],
            "triggers": res["resonance"]["triggers"],
            "factor_scores": {f["key"]: f["score"] for f in res["factors"]},
            "factor_names": {f["key"]: f["name"] for f in res["factors"]},
        })

    return {
        "market": "HK",
        "name": "港股 (恒生指数)",
        "start_date": records[0]["date"],
        "end_date": records[-1]["date"],
        "trading_days": len(records),
        "caliber_note": "100% 复现线上完整 5 因子口径：南向资金20日净流入(30%)+AH溢价(25%)+方向性VHSI(20%)+恒指趋势动量(15%)+港股流动性活跃度(10%)+5日EMA滞回+右侧拐点确认。",
        **_forward_stats(records, closes),
        "simulations": _run_simulations(records, closes, cash_rate=0.02, market="HK"),
        "split_validation": _split_validation(records, closes, cash_rate=0.02, market="HK"),
    }


def _replay_us_range(
    spx_bars: list[dict[str, Any]],
    vix_bars: list[dict[str, Any]],
    vix3m_bars: list[dict[str, Any]],
    hyg_bars: list[dict[str, Any]],
    ief_bars: list[dict[str, Any]],
    cnn_by_day: dict[str, float] | None = None,
    start_t: int = 250,
) -> tuple[list[dict[str, Any]], list[float]]:
    vix_dates = [b["date"] for b in vix_bars]
    vix3m_dates = [b["date"] for b in vix3m_bars]
    hyg_dates = [b["date"] for b in hyg_bars]
    ief_dates = [b["date"] for b in ief_bars]
    closes = [float(b["close"]) for b in spx_bars]

    records: list[dict[str, Any]] = []
    recent_scores: list[float] = []
    hyst_regime: str | None = None
    for t in range(start_t, len(spx_bars)):
        d = spx_bars[t]["date"]
        cnn_payload: dict[str, Any] = {}
        if cnn_by_day and d in cnn_by_day:
            cnn_payload = {"fear_and_greed": {"score": cnn_by_day[d], "rating": "", "timestamp": d}}

        payload = {
            "cnn": cnn_payload,
            "spx_bars": spx_bars[max(0, t - 259):t + 1],
            "vix_bars": _slice_bars_upto(vix_bars, vix_dates, d, 260),
            "vix3m_bars": _slice_bars_upto(vix3m_bars, vix3m_dates, d, 260),
            "hyg_bars": _slice_bars_upto(hyg_bars, hyg_dates, d, 30),
            "ief_bars": _slice_bars_upto(ief_bars, ief_dates, d, 30),
            "recent_scores": recent_scores[-20:],
        }
        res = score_us_market(payload, include_history=False)
        recent_scores.append(res["score"])
        tf = res.get("trend_filter")
        trend_bull = tf["above_ma200"] if isinstance(tf, dict) else None
        hyst_regime = apply_hysteresis_regime(res["smoothed_score"], hyst_regime, buffer=3.0)
        hyst_band = classify_sentiment_regime(REGIME_REP_SCORE[hyst_regime], market="US", trend_bull=trend_bull)
        records.append({
            "idx": t,
            "date": d,
            "score": res["score"],
            "smoothed_score": res["smoothed_score"],
            "regime": res["regime"],
            "hyst_regime": hyst_regime,
            "position_mid": (res["position_min"] + res["position_max"]) / 200.0,
            "hyst_position_mid": (hyst_band["position_min"] + hyst_band["position_max"]) / 200.0,
            "resonance_signal": res["resonance"]["signal"],
            "triggers": res["resonance"]["triggers"],
            "factor_scores": {f["key"]: f["score"] for f in res["factors"]},
            "factor_names": {f["key"]: f["name"] for f in res["factors"]},
        })
    return records, closes


def run_us_backtest(refresh: bool = False) -> dict[str, Any]:
    spx_bars = _load_or_fetch("us_spx", lambda: _fetch_yahoo_10y("^GSPC"), refresh)
    vix_bars = _load_or_fetch("us_vix", lambda: _fetch_yahoo_10y("^VIX"), refresh)
    vix3m_bars = _load_or_fetch("us_vix3m", lambda: _fetch_yahoo_10y("^VIX3M"), refresh)
    hyg_bars = _load_or_fetch("us_hyg", lambda: _fetch_yahoo_10y("HYG"), refresh)
    ief_bars = _load_or_fetch("us_ief", lambda: _fetch_yahoo_10y("IEF"), refresh)
    cnn_raw = _load_or_fetch("us_cnn", _fetch_cnn_fear_greed, refresh)

    records, closes = _replay_us_range(spx_bars, vix_bars, vix3m_bars, hyg_bars, ief_bars, None, 250)

    # Secondary exact-live-formula check over available CNN 1-year history
    cnn_hist = ((cnn_raw.get("fear_and_greed_historical") or {}).get("data")) or []
    cnn_by_day: dict[str, float] = {}
    for pt in cnn_hist:
        ts = pt.get("x")
        val = pt.get("y")
        if ts is not None and val is not None:
            day = datetime.fromtimestamp(float(ts) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            cnn_by_day[day] = float(val)
    cnn_start_date = min(cnn_by_day.keys()) if cnn_by_day else "9999-12-31"
    cnn_start_t = next((i for i, b in enumerate(spx_bars) if b["date"] >= cnn_start_date), len(spx_bars))
    cnn_window = None
    if cnn_start_t < len(spx_bars) - 30:
        cnn_recs, _ = _replay_us_range(
            spx_bars, vix_bars, vix3m_bars, hyg_bars, ief_bars, cnn_by_day, max(250, cnn_start_t)
        )
        cnn_window = {
            "start_date": cnn_recs[0]["date"],
            "end_date": cnn_recs[-1]["date"],
            "trading_days": len(cnn_recs),
            "stats": _forward_stats(cnn_recs, closes),
        }

    return {
        "market": "US",
        "name": "美股 (标普500)",
        "start_date": records[0]["date"],
        "end_date": records[-1]["date"],
        "trading_days": len(records),
        "caliber_note": "9年+主回测采用 Yahoo 10年数据（VIX/VIX3M 期限结构 + S&P500趋势 + HYG/IEF 信用利差 + MA200牛熊滤网 + 5日EMA滞回 + 右侧拐点确认）；另附近1年含 CNN Fear & Greed 官方历史序列的完整4因子验证。",
        **_forward_stats(records, closes),
        "simulations": _run_simulations(records, closes, cash_rate=0.03, market="US"),
        "split_validation": _split_validation(records, closes, cash_rate=0.03, market="US"),
        "cnn_1y_exact_window": cnn_window,
    }


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _render_version_comparison(results: list[dict[str, Any]]) -> list[str]:
    v1_path = ROOT / "reports" / "sentiment_backtest_v1_baseline.json"
    v2_path = ROOT / "reports" / "sentiment_backtest_v2_baseline.json"
    v1_by_m: dict[str, Any] = {}
    v2_by_m: dict[str, Any] = {}
    if v1_path.exists():
        try:
            v1_by_m = {m["market"]: m for m in json.loads(v1_path.read_text(encoding="utf-8")).get("markets", [])}
        except Exception:
            pass
    if v2_path.exists():
        try:
            v2_by_m = {m["market"]: m for m in json.loads(v2_path.read_text(encoding="utf-8")).get("markets", [])}
        except Exception:
            pass

    lines = [
        "## v1 -> v2 -> v3 调优对比（含滞回动态 & 右侧拐点）",
        "",
        "| 市场 | 版本 | 250日IC | 左侧冰点(120日胜率/均浮亏) | 右侧拐点(120日胜率/均浮亏) | 推荐动态策略年化(含现金) | 最大回撤 | 夏普 | 调仓次数 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for m in results:
        code = m["market"]
        for ver, item in [("v1 基准", v1_by_m.get(code)), ("v2 调优", v2_by_m.get(code)), ("v3 滞回+滤网", m)]:
            if not item:
                continue
            bot = item["bottom_episodes"]
            rt = item.get("right_turn_episodes")
            sims_cash = item["simulations"]["with_cash_yield"]
            sim = sims_cash.get("dynamic_hysteresis") or sims_cash["dynamic_5_tier"]
            bot_txt = f"{bot['count']}次 ({bot['r120']['win_rate']}% / {bot['avg_pain_mdd']}%)" if bot["r120"]["win_rate"] is not None else f"{bot['count']}次"
            rt_txt = f"{rt['count']}次 ({rt['r120']['win_rate']}% / {rt['avg_pain_mdd']}%)" if rt and rt["r120"]["win_rate"] is not None else "--"
            lines.append(
                f"| {code} | {ver} | `{item['ic']['ic_250d']}` | {bot_txt} | {rt_txt} | "
                f"{sim['cagr_pct']:+.2f}% | {sim['max_drawdown_pct']:.2f}% | {sim['sharpe']:.2f} | {sim['rebalances']} |"
            )

    lines.extend([
        "",
        "## 样本内外拆分验证（<=2020 样本内 vs 2021-2026 样本外）",
        "",
        "| 市场 | 阶段 | 区间 | 120日IC / 250日IC | 滞回动态年化(最大回撤/夏普/调仓) | 同仓位静态年化(回撤/夏普) | 买入持有年化(回撤/夏普) | 右侧拐点120日均值(胜率/60日均浮亏) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for m in results:
        sv = m.get("split_validation") or {}
        for key, label in [("pre_2021", "样本内(<=2020)"), ("oos_2021_2026", "样本外(2021-2026)")]:
            blk = sv.get(key)
            if not blk:
                continue
            dh = blk["simulations"]["dynamic_hysteresis"]
            st = blk["simulations"]["static_equal_exposure"]
            bh = blk["simulations"]["buy_and_hold"]
            rt = blk["right_turn_episodes"]
            rt_txt = f"{rt['r120']['mean']:+.2f}% ({rt['r120']['win_rate']}% / {rt['avg_pain_mdd']}%)" if rt["r120"]["mean"] is not None else "--"
            lines.append(
                f"| {m['market']} | {label} | `{blk['start_date']}..{blk['end_date']}` | "
                f"`{blk['ic']['ic_120d']}` / `{blk['ic']['ic_250d']}` | "
                f"{dh['cagr_pct']:+.2f}% ({dh['max_drawdown_pct']:.1f}% / {dh['sharpe']:.2f} / {dh['rebalances']}次) | "
                f"{st['cagr_pct']:+.2f}% ({st['max_drawdown_pct']:.1f}% / {st['sharpe']:.2f}) | "
                f"{bh['cagr_pct']:+.2f}% ({bh['max_drawdown_pct']:.1f}% / {bh['sharpe']:.2f}) | "
                f"{rt_txt} |"
            )
    lines.append("")
    return lines


def _render_markdown(results: list[dict[str, Any]]) -> str:
    lines: list[str] = [
        "# 大盘量化情绪指标 10 年深度回测报告",
        "",
        f"生成时间：{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
    ]
    lines.extend(_render_version_comparison(results))
    for m in results:
        lines.extend([
            f"## {m['name']} (`{m['start_date']}` 至 `{m['end_date']}`，共 {m['trading_days']} 个交易日)",
            "",
            f"> 口径说明：{m['caliber_note']}",
            "",
            f"- **情绪分与未来收益 Spearman 秩相关 (IC)**：20日 `{m['ic']['ic_20d']}` · 60日 `{m['ic']['ic_60d']}` · 120日 `{m['ic']['ic_120d']}` · 250日 `{m['ic']['ic_250d']}`（负值代表逆向指标越冷未来涨幅越高）",
            "",
            "### 1. 五档情绪分区未来收益表现",
            "",
            "| 情绪区间 | 天数 (占比) | 20日均值(胜率) | 60日均值(胜率) | 120日均值(胜率) | 250日均值(胜率) | 未来60日平均最大回撤 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ])
        for b in m["buckets"]:
            def _fmt(k_m, k_w):
                if b[k_m] is None:
                    return "--"
                return f"{b[k_m]:+.2f}% ({b[k_w]:.0f}%)"
            lines.append(
                f"| {b['label']} | {b['days']} ({b['pct_days']}%) | "
                f"{_fmt('mean_20d', 'win_20d')} | {_fmt('mean_60d', 'win_60d')} | "
                f"{_fmt('mean_120d', 'win_120d')} | {_fmt('mean_250d', 'win_250d')} | "
                f"{b['avg_mdd_60d']:+.2f}% |" if b["avg_mdd_60d"] is not None else
                f"| {b['label']} | {b['days']} ({b['pct_days']}%) | -- | -- | -- | -- | -- |"
            )

        bot = m["bottom_episodes"]
        rt = m["right_turn_episodes"]
        top = m["top_episodes"]
        lines.extend([
            "",
            "### 2. 共振信号独立事件表现（20日冷却去重）",
            "",
            f"- **左侧冰点共振**：共触发 **{bot['count']}** 次",
            f"  - 60日：均值 `{bot['r60']['mean']}%` · 中位 `{bot['r60']['median']}%` · 胜率 `{bot['r60']['win_rate']}%`",
            f"  - 120日：均值 `{bot['r120']['mean']}%` · 中位 `{bot['r120']['median']}%` · 胜率 `{bot['r120']['win_rate']}%`",
            f"  - 250日：均值 `{bot['r250']['mean']}%` · 中位 `{bot['r250']['median']}%` · 胜率 `{bot['r250']['win_rate']}%`",
            f"  - 左侧承压（触发后60日内继续最大回撤）：平均 `{bot['avg_pain_mdd']}%`，最差 `{bot['worst_pain_mdd']}%`",
            f"- **右侧拐点确认**：共触发 **{rt['count']}** 次",
            f"  - 60日：均值 `{rt['r60']['mean']}%` · 中位 `{rt['r60']['median']}%` · 胜率 `{rt['r60']['win_rate']}%`",
            f"  - 120日：均值 `{rt['r120']['mean']}%` · 中位 `{rt['r120']['median']}%` · 胜率 `{rt['r120']['win_rate']}%`",
            f"  - 250日：均值 `{rt['r250']['mean']}%` · 中位 `{rt['r250']['median']}%` · 胜率 `{rt['r250']['win_rate']}%`",
            f"  - 右侧承压（触发后60日内继续最大回撤）：平均 `{rt['avg_pain_mdd']}%`，最差 `{rt['worst_pain_mdd']}%`",
            f"- **过热预警信号**：共触发 **{top['count']}** 次",
            f"  - 60日均值 `{top['r60']['mean']}%` (胜率 `{top['r60']['win_rate']}%`) · 120日均值 `{top['r120']['mean']}%` (胜率 `{top['r120']['win_rate']}%`) · 250日均值 `{top['r250']['mean']}%` (胜率 `{top['r250']['win_rate']}%`)",
            "",
        ])
        if bot["episodes"]:
            lines.append("| 底部触发日期 | 当日点位 | 情绪分 | 60日收益 | 120日收益 | 250日收益 | 60日内最大浮亏 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")
            for ep in bot["episodes"]:
                r60 = f"{ep['ret_60d']:+.2f}%" if ep["ret_60d"] is not None else "--"
                r120 = f"{ep['ret_120d']:+.2f}%" if ep["ret_120d"] is not None else "--"
                r250 = f"{ep['ret_250d']:+.2f}%" if ep["ret_250d"] is not None else "--"
                mdd = f"{ep['mdd_60d']:+.2f}%" if ep["mdd_60d"] is not None else "--"
                lines.append(f"| {ep['date']} | {ep['price']:.2f} | {ep['score']:.1f} | {r60} | {r120} | {r250} | {mdd} |")
            lines.append("")

        lines.extend([
            "### 3. T+1 动态仓位模拟 vs 基准（含单边万五成本）",
            "",
            "| 策略（无现金收益纯择时 / 含无风险现金利息） | 总收益 | 年化 CAGR | 最大回撤 | 夏普 | 卡玛比 | 平均仓位 | 调仓次数 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ])
        for mode_label, block in [("纯择时(0%现金)", m["simulations"]["pure_timing_0_cash"]), (f"含现金({m['simulations']['with_cash_yield']['cash_yield_pct']}%)", m["simulations"]["with_cash_yield"])]:
            for key, name in [("buy_and_hold", "100% 买入持有"), ("static_equal_exposure", "同平均仓位静态"), ("dynamic_5_tier", "5档切档动态"), ("dynamic_hysteresis", "5日EMA+滞回动态"), ("dynamic_linear_weekly", "周度线性平滑")]:
                s = block[key]
                lines.append(
                    f"| {mode_label} · {name} | {s['total_return_pct']:+.2f}% | {s['cagr_pct']:+.2f}% | "
                    f"{s['max_drawdown_pct']:.2f}% | {s['sharpe']:.2f} | {s['calmar']:.2f} | "
                    f"{s['avg_exposure_pct']:.1f}% | {s['rebalances']} |"
                )

        lines.extend([
            "",
            "### 4. 单因子诊断（IC & 极冷 vs 极热 120 日收益差）",
            "",
            "| 因子 | 60日IC | 120日IC | 250日IC | 极冷(<25分)120日均值(天数) | 极热(>75分)120日均值(天数) |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for fa in m["factor_ablation"]:
            cold_txt = f"{fa['cold_120d_mean']:+.2f}% ({fa['cold_days']})" if fa["cold_120d_mean"] is not None else f"-- ({fa['cold_days']})"
            hot_txt = f"{fa['hot_120d_mean']:+.2f}% ({fa['hot_days']})" if fa["hot_120d_mean"] is not None else f"-- ({fa['hot_days']})"
            lines.append(f"| {fa['name']} | {fa['ic_60d']} | {fa['ic_120d']} | {fa['ic_250d']} | {cold_txt} | {hot_txt} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest 3-market sentiment model.")
    parser.add_argument("--refresh-cache", action="store_true", help="Re-download raw historical data.")
    args = parser.parse_args()

    print("Running 10-year point-in-time sentiment backtest...", flush=True)
    cn = run_cn_backtest(refresh=args.refresh_cache)
    print(f"[CN] {cn['start_date']}..{cn['end_date']} ({cn['trading_days']}d) IC250={cn['ic']['ic_250d']} bottom_episodes={cn['bottom_episodes']['count']}", flush=True)
    hk = run_hk_backtest(refresh=args.refresh_cache)
    print(f"[HK] {hk['start_date']}..{hk['end_date']} ({hk['trading_days']}d) IC250={hk['ic']['ic_250d']} bottom_episodes={hk['bottom_episodes']['count']}", flush=True)
    us = run_us_backtest(refresh=args.refresh_cache)
    print(f"[US] {us['start_date']}..{us['end_date']} ({us['trading_days']}d) IC250={us['ic']['ic_250d']} bottom_episodes={us['bottom_episodes']['count']}", flush=True)

    results = [cn, hk, us]
    REPORT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON_PATH.write_text(json.dumps({"generated_at": datetime.now().astimezone().isoformat(), "markets": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD_PATH.write_text(_render_markdown(results), encoding="utf-8")
    comp = _render_version_comparison(results)
    if comp:
        print("\n".join(comp), flush=True)
    print(f"Saved: {REPORT_JSON_PATH} and {REPORT_MD_PATH}", flush=True)


if __name__ == "__main__":
    main()
