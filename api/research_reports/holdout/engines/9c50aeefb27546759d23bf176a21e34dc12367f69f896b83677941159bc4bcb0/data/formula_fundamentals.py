"""Conservative SEC filing-date ledgers; never reuse future restatements."""
from __future__ import annotations
from bisect import bisect_right
from datetime import date, timedelta
from investment.data.formula_scoring import number

FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A"}


def _day(value):
    try:
        parsed = date.fromisoformat(value)
        return parsed if parsed.isoformat() == value else None
    except (ValueError, TypeError):
        return None


def _records(payload, tag, unit):
    raw = payload.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get(unit, [])
    result = []
    for row in raw:
        end, filed, start = _day(row.get("end")), _day(row.get("filed")), _day(row.get("start"))
        value = number(row.get("val"))
        if end is None or filed is None or end > filed or value is None or row.get("form") not in FORMS:
            continue
        if "start" in row and (start is None or start > end):
            continue
        result.append({"end": end.isoformat(), "filed": filed.isoformat(), "available": (filed + timedelta(days=1)).isoformat(), "start": start.isoformat() if start else None, "value": value, "accession": row.get("accn")})
    return result


def _known(records, day):
    groups = {}
    for row in records:
        if row["available"] > day:
            continue
        key = row["start"], row["end"]
        if key not in groups or row["filed"] > groups[key][0]["filed"]:
            groups[key] = [row]
        elif row["filed"] == groups[key][0]["filed"]:
            groups[key].append(row)
    # Conflicting values in one date/context are ambiguous, not averaged.
    return [{**rows[0], "value": rows[0]["value"] if len({row["value"] for row in rows}) == 1 else None} for rows in groups.values()]


def _ttm(records):
    durations = [row for row in records if row["start"]]
    annual = [row for row in durations if 330 <= (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days <= 400]
    if not annual:
        return None
    year = max(annual, key=lambda row: row["end"])
    if year["value"] is None:
        return None
    latest_end = max(row["end"] for row in durations)
    if latest_end == year["end"]:
        return {"value": year["value"], "end": year["end"], "accessions": [year["accession"]]}
    ytd = [row for row in durations if row["end"] == latest_end and 0 < (date.fromisoformat(row["start"]) - date.fromisoformat(year["end"])).days <= 8]
    if len(ytd) != 1 or ytd[0]["value"] is None:
        return None
    current = ytd[0]
    prior = [row for row in durations if 350 <= (date.fromisoformat(current["end"]) - date.fromisoformat(row["end"])).days <= 380 and abs((date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days - (date.fromisoformat(current["end"]) - date.fromisoformat(current["start"])).days) <= 14 and abs((date.fromisoformat(row["start"]) - date.fromisoformat(year["start"])).days) <= 8]
    if len(prior) != 1 or prior[0]["value"] is None:
        return None
    return {"value": year["value"] + current["value"] - prior[0]["value"], "end": current["end"], "accessions": [year["accession"], current["accession"], prior[0]["accession"]]}


def build_ledger(payload: dict) -> list[dict]:
    income = _records(payload, "NetIncomeLoss", "USD")
    shares = _records(payload, "CommonStockSharesOutstanding", "shares")
    equity = _records(payload, "StockholdersEquity", "USD")
    ledger = []
    for day in sorted({row["available"] for row in income + shares + equity}):
        known_shares = _known(shares, day); known_equity = _known(equity, day)
        share = max(known_shares, key=lambda row: row["end"], default=None)
        book = max(known_equity, key=lambda row: row["end"], default=None)
        ledger.append({"available": day, "shares": share, "book": book, "ttm_income": _ttm(_known(income, day)), "source": "SEC companyfacts us-gaap", "cik": payload.get("cik")})
    return ledger


def valuation_at(ledger: list[dict], day: str, raw_close: float | None, *, last_split: str | None = None) -> dict:
    price = number(raw_close); current = _day(day)
    if price is None or price <= 0 or current is None or not ledger:
        return {}
    index = bisect_right([row["available"] for row in ledger], day) - 1
    if index < 0:
        return {}
    point = ledger[index]; shares = point["shares"]
    if not shares or shares["value"] is None or shares["value"] <= 0 or (current - date.fromisoformat(shares["end"])).days > 400 or (last_split and shares["end"] < last_split):
        return {}
    cap = price * shares["value"]
    result = {"market_cap": cap, "metrics_as_of": point["available"], "fundamentals_source": point["source"], "shares_period_end": shares["end"], "fundamentals_accessions": [shares["accession"]]}
    income = point["ttm_income"]
    if income and income["value"] != 0 and (current - date.fromisoformat(income["end"])).days <= 400:
        result.update(pe_ratio=cap / income["value"], earnings_period_end=income["end"])
        result["fundamentals_accessions"].extend(income["accessions"])
    book = point["book"]
    if book and book["value"] is not None and book["value"] > 0 and abs((date.fromisoformat(shares["end"]) - date.fromisoformat(book["end"])).days) <= 8 and (current - date.fromisoformat(book["end"])).days <= 400:
        result.update(pb_ratio=cap / book["value"], book_period_end=book["end"])
        result["fundamentals_accessions"].append(book["accession"])
    return result


def attach_ledger(bars: list[dict], ledger: list[dict]) -> list[dict]:
    result = []; previous_scale = None; last_split = None
    for original in bars:
        row = {key: value for key, value in original.items() if key not in {"pe_ratio", "pb_ratio", "market_cap", "metrics_as_of"}}
        scale = number(row.get("share_scale"))
        if scale is not None and scale > 0:
            if previous_scale is not None and abs(scale / previous_scale - 1) > .2:
                # A split or a large adjustment discontinuity makes earlier
                # share counts unsafe. Wait for a later balance-period count.
                last_split = row["date"]
            previous_scale = scale
        row.update(valuation_at(ledger, row["date"], row.get("raw_close"), last_split=last_split))
        result.append(row)
    return result
