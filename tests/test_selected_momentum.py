from datetime import datetime, timezone
import pytest
from data.selected_momentum import POLICY, market_gate, entry_size, holding_action


def test_selected_parameters_are_the_reported_policy():
    assert POLICY['max_positions']==20
    assert POLICY['hold_days']==20 and POLICY['stop_pct']==.12
    assert POLICY['momentum_weeks']==12 and POLICY['ma_period']==120
    assert POLICY['daily_refill'] is False and POLICY['momentum_rank']==0


def test_market_requires_valid_uncompressed_window():
    assert market_gate([100.]*119+[101.])['allow_open']
    assert not market_gate([100.]*120)['allow_open']
    assert not market_gate([100.]*119+[None])['ready']


def test_size_respects_cash_fees_lots_and_target():
    r=entry_size(100000,1100,10)
    assert r['shares']==100 and r['estimated_cost']<=1100
    assert r['target_amount']==5000
    assert entry_size(100000,900,10)['shares']==0
    with pytest.raises(ValueError):entry_size(100000,-1,10)


def test_missing_quote_or_entry_date_does_not_invent_exit():
    assert holding_action(10,None,False,None,False)['action']=='verify'
    assert holding_action(10,11,True,None,False)['action']=='verify'


def test_stop_t1_and_actual_backtest_time_counter():
    assert holding_action(10,8.7,True,2,False)['action']=='stop'
    assert holding_action(10,8.7,True,0,True)['action']=='t1_blocked'
    # Backtest checks held>=20 before incrementing it; day after entry starts at zero.
    assert holding_action(10,11,True,20,False)['action']=='hold'
    assert holding_action(10,11,True,21,False)['action']=='time_at_close'


def test_latest_week_ranking_matches_original_feature_formula():
    import pandas as pd
    import numpy as np
    from scripts.build_selected_momentum import ranked_rows
    # Independent formula check, with unsorted input and future rows present.
    days=pd.bdate_range('2023-01-02','2024-02-02')
    frame=pd.DataFrame({'date':days,'code':'sz000001','close':np.arange(len(days))+100.,
                        'high':np.arange(len(days))+101.,'low':np.arange(len(days))+99.})
    day='2024-01-26'
    rows=ranked_rows(frame.sample(frac=1,random_state=4),day,{'sz000001':'平安银行'})
    closes=frame[frame.date<=day].set_index('date').close.resample('W-FRI').last()
    expected=float(np.float32(closes.iloc[-1]/closes.iloc[-13]-1))*100
    assert rows[0]['momentum_pct']==expected
    changed=frame.copy();changed.loc[changed.date>day,'close']=1e9
    assert ranked_rows(changed,day,{'sz000001':'平安银行'})==rows


def test_snapshot_identity_matches_stored_report():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    snapshot=json.loads((root/'api/research_reports/momentum-selected.json').read_text(encoding='utf-8'))
    full=next(r for r in snapshot['backtest']['results'] if r['period']=='full')
    assert (full['total_return_pct'],full['cagr_pct'],full['max_drawdown_pct'])==(527.879,17.525,-26.326)
    assert snapshot['universe_size']==793
    assert snapshot['policy']==POLICY
    assert snapshot['automation_enabled'] is False
    assert all(c['native_quote'] is None or c['native_quote']['price_basis']=='unadjusted' for c in snapshot['candidates'])


def test_public_routes_return_policy_and_reject_invalid_money():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routes.selected_momentum import router
    app=FastAPI();app.include_router(router)
    client=TestClient(app)
    r=client.get('/strategy/momentum-selected');assert r.status_code==200
    assert r.json()['version']==POLICY['version']
    assert r.json()['scope']=='reference793'
    assert r.json()['universe_size']==793
    assert next(row for row in r.json()['backtest']['results'] if row['period']=='full')['total_return_pct']==527.879
    assert client.get('/strategy/momentum-selected?scope=mainboard').json()['backtest']['results']==[]
    assert client.post('/strategy/momentum-selected/size',json={'equity':1000,'cash':2000,'native_price':10}).status_code==422
    assert client.post('/strategy/momentum-selected/size',json={'equity':100000,'cash':1100,'native_price':10}).json()['shares']==100


def test_expired_snapshot_blocks_new_positions(monkeypatch):
    import api.routes.selected_momentum as route
    class Future:
        @staticmethod
        def now(tz):return datetime(2030,1,1,tzinfo=tz)
    monkeypatch.setattr(route,'datetime',Future)
    result=route.selected_policy()
    assert result['snapshot_fresh'] is False
    assert result['allow_new_by_snapshot'] is False
