"""Attach live momentum provenance without changing the frozen historical adapter."""
import copy
import time
from concurrent.futures import ThreadPoolExecutor, wait
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


def enrich_foreign_history(rows, *, as_of=None, limit=120, history_timeout=45):
    if rows and all(row.get('market') == 'US' and 'quote_as_of' in row for row in rows):
        selected = sorted(rows, key=lambda row: base.number(row.get('amount')) or 0, reverse=True)[:limit]
        def enrich_one(row):
            result = base.enrich_foreign_history([row], as_of=row.get('quote_as_of') or as_of, limit=1)
            return result[0]
        executor = ThreadPoolExecutor(max_workers=8)
        futures = {row['ticker']: executor.submit(enrich_one, row) for row in selected}
        completed, pending = wait(futures.values(), timeout=history_timeout)
        executor.shutdown(wait=False, cancel_futures=True)
        enriched = []
        for row in selected:
            future = futures[row['ticker']]
            if future in completed and future.exception() is None:
                enriched.append(future.result())
            else:
                clean = {key:value for key,value in row.items() if key not in ('change_5d','change_20d','change_60d','risk_bars','history_as_of','trend_history')}
                enriched.append({**clean, 'history_budget_exceeded': future in pending,
                                 'history_error': '本轮历史计算达到45秒上限，未补填趋势或保护价' if future in pending else '历史数据暂不可用，未补填趋势或保护价'})
        clocks = {row['ticker']: row.get('quote_as_of') for row in selected}
        enriched = [{**row, 'quote_as_of': clocks[row['ticker']]} for row in enriched]
    else:
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
