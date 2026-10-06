"""Native A-share history; vendor valuations are explicit unverified references."""
from collections import Counter
from investment.data.formula_scoring import number


def normalize_history(raw: list[dict], adjusted: list[dict]) -> dict:
    by_date = {row["date"]: row for row in adjusted}
    bars = []; excluded = Counter()
    for original in sorted(raw, key=lambda row: row["date"]):
        if original.get("tradestatus") != "1":
            excluded["suspended"] += 1; continue
        row = by_date.get(original["date"])
        if row is None:
            excluded["missing_adjusted_bar"] += 1; continue
        values = {key: number(row.get(key)) for key in ("open", "high", "low", "close")}
        raw_close = number(original.get("close"))
        if raw_close is None or raw_close <= 0 or any(value is None or value <= 0 for value in values.values()):
            raise ValueError(f"Invalid active price at {original['date']}")
        if values["high"] < max(values["open"], values["close"], values["low"]) or values["low"] > min(values["open"], values["close"]):
            raise ValueError(f"Invalid OHLC at {original['date']}")
        reference = {field: number(original.get(tag)) for field, tag in (("pe_ratio", "peTTM"), ("pb_ratio", "pbMRQ"), ("turnover_rate", "turn")) if number(original.get(tag)) is not None}
        bars.append({"date": original["date"], **values, "volume": number(original.get("volume")), "raw_close": raw_close, "share_scale": raw_close / values["close"], "historical_reference": reference})
    return {"bars": bars, "input_count": len(raw), "excluded_by_reason": dict(excluded), "source": "BaoStock未复权＋前复权日K", "reference_basis": "日K接口peTTM、pbMRQ、turn；财务修订版本时间未验证，不作为严格PIT估值"}
