import json
from datetime import datetime, timezone
import pytest
from investment.data import foreign_live_scanner as live
from investment.api.routes import ai_screener as api


def snapshot(stamp='2026-10-02T19:38:14.892Z'):
    return {'market':'HK','generated_at':stamp,'source':'actual provider snapshot',
        'rows':[{'ticker':f'hk{i:05d}','market':'HK','currency':'HKD','price':10,'amount':900000000,
                 'name':'普通股','market_cap':20000000000,'instrument_type':'stock'} for i in range(1,21)]}


def test_primary_preserved(monkeypatch):
    payload={'market':'HK','rows':[]}
    monkeypatch.setattr(live.base,'scan_foreign_market',lambda market:payload)
    assert live.scan_foreign_market('HK') is payload


def test_saved_hk_preserves_generation_date_but_does_not_invent_quote_dates(tmp_path):
    path=tmp_path/'hk.json';path.write_text(json.dumps(snapshot()),encoding='utf-8')
    result=live.read_hk_snapshot(path,now=datetime(2026,10,5,tzinfo=timezone.utc))
    assert result['generated_at']=='2026-10-02T19:38:14.892Z'
    assert result['cached'] and result['stale']
    assert all(row['quote_as_of'] is None for row in result['rows'])
    assert '报价日期未核实' in result['source']


@pytest.mark.parametrize('stamp',['2026-09-20T00:00:00Z','2026-10-06T00:00:00Z',None,'invalid','2026-10-02'])
def test_invalid_future_or_expired_snapshot_fails_closed(tmp_path,stamp):
    path=tmp_path/'hk.json';path.write_text(json.dumps(snapshot(stamp)),encoding='utf-8')
    with pytest.raises((ValueError,RuntimeError)): live.read_hk_snapshot(path,now=datetime(2026,10,5,tzinfo=timezone.utc))


@pytest.mark.parametrize('failure',['currency','market','duplicate','insufficient','infinite','nonstock'])
def test_invalid_universe_is_rejected(tmp_path,failure):
    payload=snapshot()
    if failure=='currency':payload['rows'][0]['currency']='CNY'
    if failure=='market':payload['rows'][0]['market']='US'
    if failure=='duplicate':payload['rows'].append(dict(payload['rows'][0]))
    if failure=='insufficient':payload['rows']=payload['rows'][:1]
    if failure=='infinite':payload['rows'][0]['price']=float('inf')
    if failure=='nonstock':
        for row in payload['rows']:row.update(instrument_type='etf',name='ETF基金')
    path=tmp_path/'hk.json';path.write_text(json.dumps(payload),encoding='utf-8')
    with pytest.raises((ValueError,RuntimeError)):live.read_hk_snapshot(path,now=datetime(2026,10,5,tzinfo=timezone.utc))


def test_unknown_native_quote_time_stays_unknown_after_history_enrichment(monkeypatch):
    monkeypatch.setattr(api,'enrich_foreign_history',lambda rows,**kwargs:[{**row,'quote_as_of':kwargs['as_of']} for row in rows])
    rows=[{'ticker':'hk00700','market':'HK','price':500,'quote_as_of':None}]
    assert api.enrich_screen_history(rows,'HK','2026-10-02T19:38:14.892Z')[0]['quote_as_of'] is None


def test_us_uses_validated_full_snapshot_and_never_active_100(monkeypatch):
    from investment.data import us_universe
    payload={'market':'US','universe_count':5000,'rows':[]}
    monkeypatch.setattr(us_universe,'read_us_snapshot',lambda:payload)
    monkeypatch.setattr(live.base,'scan_foreign_market',lambda market:pytest.fail('不能再读取活跃100只'))
    assert live.scan_foreign_market('US') is payload


@pytest.mark.parametrize('stamp',[None,True,-1,'2100-01-01T00:00:00Z','2026-10-05'])
def test_invalid_or_future_us_quote_clock_rejects_full_snapshot(tmp_path,stamp):
    from investment.data import us_universe
    now=datetime.now(timezone.utc).isoformat()
    identity={'ticker':'AAPL','exchange':'NASDAQ','instrument_type':'stock'}
    payload={'version':'us-universe-v1','market':'US','generated_at':now,'directory_generated_at':now,
             'directory':[identity], 'rows':[{**identity,'market':'US','currency':'USD','price':10,'quote_as_of':stamp}]}
    path=tmp_path/'us.json';path.write_text(json.dumps(payload),encoding='utf-8')
    with pytest.raises(ValueError): us_universe.read_us_snapshot(path)


def test_live_hk_without_provider_clock_is_unverified(monkeypatch):
    monkeypatch.setattr(live.base,'scan_foreign_market',lambda market:{'rows':[{'ticker':'hk00700','price':500}],
                        'generated_at':'2026-10-05T00:00:00Z'})
    assert live.scan_foreign_market('HK')['rows'][0]['quote_as_of'] is None
