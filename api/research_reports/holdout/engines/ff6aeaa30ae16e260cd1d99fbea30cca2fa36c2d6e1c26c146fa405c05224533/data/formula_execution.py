"""Opt-in capital, minimum fee and raw-price entry-step research assumptions."""
import math
import re
from datetime import date
from urllib.parse import urlparse
from investment.data.formula_scoring import number


def validate_lot_ledger(ledger):
    if not isinstance(ledger, dict) or not ledger:
        raise ValueError("Lot reference ledger must be a nonempty security map")
    for ticker, points in ledger.items():
        if not isinstance(ticker, str) or not re.fullmatch(r"hk\d{5}", ticker) or not isinstance(points, list) or not points:
            raise ValueError("Invalid lot reference security or points")
        previous_end = None
        for point in points:
            if not isinstance(point, dict) or set(point) != {"published_on", "known_after", "effective_from", "valid_until", "lot_size", "source"}:
                raise ValueError("Invalid lot reference fields")
            if any(not isinstance(point[key], str) for key in ("published_on", "known_after", "effective_from", "valid_until", "source")):
                raise ValueError("Lot reference dates and source must be strings")
            stamps = {key: date.fromisoformat(point[key]) for key in ("published_on", "known_after", "effective_from", "valid_until")}
            if any(value.isoformat() != point[key] for key, value in stamps.items()):
                raise ValueError("Noncanonical lot reference date")
            if stamps["known_after"] <= stamps["published_on"] or stamps["valid_until"] < max(stamps["effective_from"], stamps["known_after"]) or (stamps["valid_until"] - stamps["effective_from"]).days > 31:
                raise ValueError("Invalid or unbounded lot reference availability")
            if previous_end is not None and stamps["effective_from"] <= previous_end:
                raise ValueError("Overlapping or unordered lot reference intervals")
            previous_end = stamps["valid_until"]
            lot = point["lot_size"]
            source = urlparse(point["source"])
            if isinstance(lot, bool) or not isinstance(lot, int) or lot <= 0 or source.scheme != "https" or source.hostname not in ("www.hkexnews.hk", "www1.hkexnews.hk"):
                raise ValueError("Invalid lot size or announcement source")
    return ledger


def lot_reference(config, ticker, day):
    for point in config.get("lot_ledger", {}).get(ticker, []):
        if point["effective_from"] <= day <= point["valid_until"] and point["known_after"] <= day:
            return point
    return None


def lot_reference_coverage(series, config):
    if not config or "lot_ledger" not in config:
        return None
    counts = {ticker: sum(lot_reference(config, ticker, bar["date"]) is not None for bar in bars[61:]) for ticker, bars in series.items()}
    return {"basis": "公告短区间参考；披露日次日起可用，不是完整历史整手规则", "observations": sum(max(0, len(bars) - 61) for bars in series.values()), "available": sum(counts.values()), "by_security": counts}


def validate_execution(config, markets):
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) - {"market", "initial_capital", "minimum_fee", "entry_lot_size", "lot_ledger"}:
        raise ValueError("Unknown execution scenario fields")
    capital, fee, lot = config.get("initial_capital"), config.get("minimum_fee", 0), config.get("entry_lot_size")
    if config.get("market") not in ("CN", "HK", "US") or markets != {config.get("market")}:
        raise ValueError("Execution scenario requires one matching market/currency")
    if number(capital) is None or capital <= 0 or number(fee) is None or fee < 0 or fee >= capital:
        raise ValueError("Invalid capital or minimum fee")
    if lot is not None and (isinstance(lot, bool) or not isinstance(lot, int) or lot < 1):
        raise ValueError("Entry lot size must be a positive integer")
    extra = {}
    if "lot_ledger" in config:
        if config["market"] != "HK" or lot is not None:
            raise ValueError("Dated HK lot references cannot use a constant fallback")
        extra["lot_ledger"] = validate_lot_ledger(config["lot_ledger"])
    return {"market": config["market"], "initial_capital": capital, "minimum_fee": fee, "entry_lot_size": lot, **extra}


def order_fee(notional, rate, config):
    return max(notional * rate, config["minimum_fee"] / config["initial_capital"]) if config else notional * rate


def entry_order(allocation, bar, rate, config, *, risk_budget=None, loss_fraction=None, ticker=None, trade_date=None):
    minimum = config["minimum_fee"] / config["initial_capital"] if config else 0
    notional = min(allocation / (1 + rate), allocation - minimum)
    if risk_budget is not None:
        if number(risk_budget) is None or risk_budget < 0 or number(loss_fraction) is None or not 0 < loss_fraction < 1:
            raise ValueError("Invalid stop risk budget")
        if risk_budget <= 2 * minimum:
            return {"status": "below_minimum_fee"}
        low, high = 0.0, max(0, notional)
        for _ in range(60):
            mid = low + (high - low) / 2
            loss = mid * loss_fraction + order_fee(mid, rate, config) + order_fee(mid * (1 - loss_fraction), rate, config)
            if loss <= risk_budget:
                low = mid
            else:
                high = mid
        notional = low
    result = {}
    lot_size = config["entry_lot_size"] if config else None
    if config and "lot_ledger" in config:
        point = lot_reference(config, ticker, trade_date) if ticker and trade_date else None
        if point is None:
            return {"status": "unverified_lot"}
        lot_size = point["lot_size"]
        result["lot_reference"] = point
    if lot_size is not None:
        raw_close = number(bar.get("raw_close"))
        if raw_close is None or raw_close <= 0:
            return {"status": "unverified_raw_price"}
        raw_open = bar["open"] * raw_close / bar["close"]
        if not math.isfinite(raw_open) or raw_open <= 0:
            return {"status": "unverified_raw_price"}
        lot_notional = raw_open * lot_size / config["initial_capital"]
        lots = math.floor(max(0, notional) / lot_notional)
        if lots == 0:
            return {"status": "below_entry_lot"}
        notional = lots * lot_notional
        result["raw_entry_quantity"] = lots * lot_size
    if notional <= 0:
        return {"status": "below_minimum_fee"}
    fee = order_fee(notional, rate, config)
    return {"status": "ok", "notional": notional, "fee": fee, **result}
