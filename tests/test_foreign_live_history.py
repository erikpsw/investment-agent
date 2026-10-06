import copy
from datetime import date, timedelta
import time
from unittest.mock import patch
import pytest
from investment.data import foreign_formula as base
from investment.data.foreign_live_history import enrich_foreign_history
from investment.api.history_price_metadata import history_price_metadata
from investment.data.formula_scoring import score_item


def fixture(source="Yahoo",basis="adjusted",market="US"):
    ticker="AAPL" if market=="US" else "hk00700"
    bars=[{"date":(date(2026,6,1)+timedelta(days=i)).isoformat(),"open":100+i,"high":101+i,
           "low":99+i,"close":100+i,"history_source":source,"price_basis":basis,
           "raw_close":(100+i)*2 if source=="Yahoo" else None} for i in range(75)]
    stamp=bars[-1]["date"]
    row={"ticker":ticker,"market":market,"price":348,"quote_as_of":stamp,"history_as_of":stamp,
         **{f"change_{n}d":round((bars[-1]["close"]/bars[-n-1]["close"]-1)*100,2) for n in (5,20,60)},
         "risk_bars":copy.deepcopy(base._live_risk_bars(bars))}
    return row,bars,(market,ticker,stamp)


@pytest.mark.parametrize("source,basis,market",[("Yahoo","adjusted","US"),("Tencent","qfq","HK"),("Tencent","raw","US")])
def test_records_full_window_and_keeps_prices_and_scores(source,basis,market):
    row,bars,key=fixture(source,basis,market); before=copy.deepcopy((row,bars))
    with patch.object(base,"enrich_foreign_history",return_value=[row]),patch.dict(base._cache,{key:(time.time(),bars)},clear=True):
        output=enrich_foreign_history([{"ticker":row["ticker"]}],as_of=key[-1])[0]
    provenance=output["trend_history"]
    assert provenance["source"]==source and provenance["price_basis"]==basis and provenance["bar_count"]==61
    assert provenance["window_start"]==bars[-61]["date"] and provenance["window_end"]==bars[-1]["date"]
    metadata=history_price_metadata(output)
    assert metadata["trend"]["status"]=="reported" and metadata["trend"]["price_basis"]==basis
    assert metadata["protection"]["status"]=="reported"
    if source=="Yahoo": assert metadata["protection"]["price_basis"]=="latest_raw_close_reference"
    for mode in ("balanced","conservative","aggressive"):
        scored=score_item(output,mode);scored.pop("trend_history")
        assert scored==score_item(row,mode)
    assert (row,bars)==before


@pytest.mark.parametrize("problem",["missing","expired","mixed","unmarked","short","wrong_factor","wrong_risk","wrong_date"])
def test_unavailable_or_inconsistent_full_window_does_not_reuse_stale_provenance(problem):
    row,bars,key=fixture(); row["trend_history"]={"source":"Tencent","price_basis":"qfq","status":"reported"}
    cache={key:(time.time(),bars)}
    if problem=="missing": cache={}
    elif problem=="expired": cache[key]=(time.time()-601,bars)
    elif problem=="mixed": bars[-61]["price_basis"]="raw"
    elif problem=="unmarked": bars[-61].pop("history_source")
    elif problem=="short": cache[key]=(time.time(),bars[-60:])
    elif problem=="wrong_factor": row["change_60d"]+=1
    elif problem=="wrong_risk": row["risk_bars"][0]["high"]+=1
    elif problem=="wrong_date": row["history_as_of"]="2026-01-01"
    with patch.object(base,"enrich_foreign_history",return_value=[row]),patch.dict(base._cache,cache,clear=True),patch.object(base.requests,"get",side_effect=AssertionError("No additional request")):
        output=enrich_foreign_history([],as_of=key[-1])[0]
    assert "trend_history" not in output
    assert history_price_metadata(output)["trend"]["status"]=="unverified"
    assert output["risk_bars"]==row["risk_bars"]


@pytest.mark.parametrize("field,value",[("source",{}),("price_basis",[]),("window_start","bad"),("window_end",None),("bar_count",60)])
def test_malformed_provenance_stays_unverified(field,value):
    row,bars,key=fixture()
    row["trend_history"]={"version":"foreign-trend-window-v1","status":"reported","source":"Yahoo","price_basis":"adjusted",
                          "bar_count":61,"window_start":bars[-61]["date"],"window_end":bars[-1]["date"],field:value}
    assert history_price_metadata(row)["trend"]["status"]=="unverified"


def test_us_history_uses_each_original_quote_clock_and_preserves_it():
    rows=[{'ticker':'AAPL','market':'US','amount':10,'quote_as_of':'2026-10-02T16:00:00-04:00'},
          {'ticker':'MSFT','market':'US','amount':20,'quote_as_of':'2026-10-05T16:00:00-04:00'}]
    calls=[]
    def enrich(values,**kwargs):
        calls.append(kwargs['as_of'])
        return [{**row,'quote_as_of':kwargs['as_of']} for row in values]
    with patch.object(base,'enrich_foreign_history',side_effect=enrich):
        output=enrich_foreign_history(rows,as_of='2026-10-06T00:00:00Z',limit=120)
    assert set(calls)=={row['quote_as_of'] for row in rows}
    assert {row['ticker']:row['quote_as_of'] for row in output}=={row['ticker']:row['quote_as_of'] for row in rows}


def test_us_slow_history_returns_completed_rows_with_explicit_missing_factors():
    import threading
    release=threading.Event()
    rows=[{'ticker':ticker,'market':'US','amount':10,'quote_as_of':'2026-10-05T16:00:00-04:00'} for ticker in ('FAST','SLOW')]
    def enrich(values,**kwargs):
        row=values[0]
        if row['ticker']=='SLOW': release.wait(2)
        return [{**row,'change_5d':2,'change_20d':3,'change_60d':4}]
    started=time.monotonic()
    try:
        with patch.object(base,'enrich_foreign_history',side_effect=enrich):
            output=enrich_foreign_history(rows,history_timeout=.05)
        assert time.monotonic()-started < .4
        by_ticker={row['ticker']:row for row in output}
        assert by_ticker['FAST']['change_20d']==3
        assert by_ticker['SLOW']['history_budget_exceeded'] is True
        assert 'change_20d' not in by_ticker['SLOW'] and 'risk_bars' not in by_ticker['SLOW']
    finally:
        release.set()
