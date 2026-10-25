from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from data.stock_reanalysis import analyze, parse_bars


def series():
    day=datetime(2025,1,1)
    return [[(day+timedelta(days=i)).date().isoformat(),10+i/100,11+i/100,9+i/100,10+i/100,100] for i in range(660) if (day+timedelta(days=i)).weekday()<5]


def test_unfinished_day_excluded_and_market_blocks_entry():
    bars=series();now=datetime.fromisoformat(bars[-1][0]+'T10:00:00').replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    result=analyze(bars,bars,now)
    assert result['bars'][-1][0]<now.date().isoformat()
    assert result['momentum_pct'] is not None
    falling=[[b[0],100-i/100,101-i/100,99-i/100,100-i/100,b[5]] for i,b in enumerate(bars)]
    assert not analyze(bars,falling,now)['market']['allow_open']


def test_incomplete_week_cannot_change_weekly_signal():
    bars=series();now=datetime(2026,10,26,10,tzinfo=ZoneInfo('Asia/Shanghai'))
    first=analyze(bars,bars,now)
    extra=['2026-10-26',999,1000,998,999,100]
    second=analyze(bars+[extra],bars+[extra],now)
    assert first['momentum_pct']==second['momentum_pct']


def test_wrong_basis_and_invalid_candle_rejected():
    with pytest.raises(ValueError):parse_bars({'code':0,'data':{'sz002027':{'day':[['2026-10-23','1','2','3','0.5','100']]}}},'sz002027','hfq')
    with pytest.raises(ValueError):parse_bars({'code':0,'data':{'sz002027':{'hfqday':[['2026-10-23','1','2','1','0.5','100']]}}},'sz002027','hfq')


def test_api_reanalysis_refetches_both_series_and_fails_closed(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api.routes.selected_momentum as route
    calls=[]
    class Reply:
        def raise_for_status(self):pass
        def json(self):
            code,basis=calls[-1]
            return {'code':0,'data':{code:{'hfqday' if basis=='hfq' else 'day':[[b[0],b[1],b[4],b[2],b[3],b[5]] for b in series()]}}}
    # Sequential execution makes the fixture deterministic; the production fetches run concurrently.
    class Pool:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def map(self,fn,items):return map(fn,items)
    def get(url,params,timeout,verify):
        assert verify is True
        fields=params['param'].split(',');calls.append((fields[0],fields[-1]));return Reply()
    monkeypatch.setattr(route,'ThreadPoolExecutor',Pool)
    monkeypatch.setattr(route.requests,'get',get)
    app=FastAPI();app.include_router(route.router);client=TestClient(app)
    for _ in range(2):assert client.get('/strategy/reanalyze/sz002027').status_code==200
    assert len(calls)==4
    assert client.get('/strategy/reanalyze/invalid').status_code==422
    monkeypatch.setattr(route.requests,'get',lambda *a,**kw:(_ for _ in ()).throw(ValueError('offline')))
    r=client.get('/strategy/reanalyze/sz002027');assert r.status_code==503
    assert 'momentum_pct' not in r.json()
