"""Deterministic current-universe samples, independent of prices and returns."""
from __future__ import annotations
import re
from investment.data.formula_instruments import stock_candidates


def frozen_sample(report: dict, market: str) -> dict:
    """Replay the requested pool, including failures, without reclassifying today."""
    if not isinstance(report, dict) or market not in ("CN", "HK", "US") or report.get("market") != market:
        raise ValueError("样本清单市场不匹配")
    original = report.get("sampling") or {}
    if not isinstance(original, dict):
        raise ValueError("报告抽样记录格式错误")
    selected = original.get("selected")
    if selected is None:
        selected = report.get("universe")
        if not isinstance(selected, list) or report.get("requested_count") != len(selected):
            raise ValueError("报告只有成功样本，缺少完整请求名单")
    patterns = {"CN": r"(?:sh60\d{4}|sz00\d{4})", "HK": r"hk\d{5}", "US": r"[A-Z][A-Z0-9.-]{0,14}"}
    if not isinstance(selected, list) or not 1 <= len(selected) <= 200 or any(not isinstance(t, str) or not re.fullmatch(patterns[market], t) for t in selected) or len(set(selected)) != len(selected):
        raise ValueError("样本名单为空、重复、超限或代码不合法")
    if report.get("requested_count", len(selected)) != len(selected):
        raise ValueError("请求数量与样本清单不一致")
    return {**original, "selected": list(selected), "original_method": original.get("method"), "method": "冻结既有报告请求样本；不读取当前行情、目录或收益重新抽样"}


def select_sample(rows: list[dict], market: str, size: int) -> dict:
    if market not in ("CN", "HK", "US") or not 8 <= size <= 200:
        raise ValueError("Invalid sampling market or size")
    matching = [row for row in rows if row.get("market") == market]
    filtered = stock_candidates(matching)
    eligible = filtered.pop("rows")
    filtered.pop("excluded")  # Keep counts; do not ship entire exchange directories.
    scoped = []
    for row in eligible:
        ticker = row["ticker"]
        if market == "CN" and (not re.fullmatch(r"(?:sh60\d{4}|sz00\d{4})", ticker) or "ST" in row.get("name", "").upper()):
            continue
        scoped.append(row)
    # Sort and deduplicate before sampling; source row order cannot affect it.
    by_ticker = {row["ticker"]: row for row in sorted(scoped, key=lambda row: (row["ticker"], str(row.get("name", ""))))}
    codes = sorted(by_ticker)
    count = min(len(codes), size)
    selected = [codes[i * len(codes) // count] for i in range(count)]
    return {**filtered, "scope_excluded_count": len(eligible) - len(scoped), "eligible_count": len(codes), "selected": selected, "selected_metadata": [{"ticker": ticker, **{key: by_ticker[ticker].get(key) for key in ("classification_source", "classification_as_of")}} for ticker in selected], "method": "证券代码排序后等距抽样；不读取价格、成交额、涨幅或历史收益"}
