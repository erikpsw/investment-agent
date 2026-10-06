"""Attach live momentum provenance without changing the frozen historical adapter."""
import copy
import time
from investment.data import foreign_formula as base


def _provenance(row):
    if row.get("market") not in ("HK", "US") or not row.get("history_as_of"):
        return None
    key = (row["market"], row["ticker"], base.completed_date(row.get("quote_as_of"), row["market"]))
    cached = base._cache.get(key)
    if not cached or time.time()-cached[0] >= 600:
        return None
    bars = copy.deepcopy(cached[1])
    if len(bars) < 61 or bars[-1].get("date") != row["history_as_of"]:
        return None
    if base._validated_bars(bars, row["history_as_of"]) != bars:
        return None
    window = bars[-61:]
    pairs = {(bar.get("history_source"),bar.get("price_basis")) for bar in window}
    if len(pairs) != 1 or not pairs.issubset({("Tencent","qfq"),("Tencent","raw"),("Yahoo","adjusted")}):
        return None
    if any(row.get(f"change_{n}d") != round((bars[-1]["close"]/bars[-n-1]["close"]-1)*100,2) for n in (5,20,60)):
        return None
    if row.get("risk_bars") != base._live_risk_bars(copy.deepcopy(bars)):
        return None
    source,basis = next(iter(pairs))
    return {"version":"foreign-trend-window-v1", "status":"reported", "source":source,"price_basis":basis,
            "bar_count":61,"window_start":window[0]["date"],"window_end":window[-1]["date"]}


def enrich_foreign_history(rows, *, as_of=None, limit=120):
    enriched = base.enrich_foreign_history(rows, as_of=as_of, limit=limit)
    output=[]
    for original in enriched:
        row={key:value for key,value in original.items() if key != "trend_history"}
        try:
            provenance=_provenance(row)
        except (KeyError,TypeError,ValueError,RuntimeError,OverflowError,ZeroDivisionError):
            provenance=None
        if provenance: row["trend_history"]=provenance
        output.append(row)
    return output
