from datetime import datetime, timezone
from types import SimpleNamespace
import copy
import pytest
import requests
from investment.data import screener_snapshot_store as cache


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(cache,'_now',lambda:datetime(2026,10,5,tzinfo=timezone.utc))


def snapshot():
    return {'market':'US','source':'synthetic provider','generated_at':'2026-10-02T20:00:00+00:00',
      'rows':[{'ticker':f'T{i}','market':'US','currency':'USD','instrument_type':'stock','name':'合成股票',
               'price':100,'amount':1000000,'quote_time':datetime(2026,10,2,20,tzinfo=timezone.utc).timestamp()} for i in range(12)]}


def test_remote_read_revalidates_dates_and_preserves_original_clock(monkeypatch):
    payload=snapshot();captured={}
    def post(url,**kwargs):captured.update(kwargs);return SimpleNamespace(status_code=200,json=lambda:payload)
    monkeypatch.setattr(cache.requests,'post',post)
    result=cache.CloudSnapshotStore('https://example.test','synthetic-key').load('US')
    assert result['generated_at']==payload['generated_at'] and result['cached']
    assert all(row['quote_as_of']=='2026-10-02T20:00:00+00:00' for row in result['rows'])
    assert captured['json']=={'operation':'get','market_name':'US','payload':None}
    assert captured['timeout']==5
    assert captured['allow_redirects'] is False


def test_saved_fallback_is_not_written_as_a_new_live_observation(monkeypatch):
    monkeypatch.setattr(cache,'snapshot_store',lambda:SimpleNamespace(save=lambda *args:pytest.fail('旧缓存不能重新写成新抓取')))
    for flag in ['cached','stale']:
        assert cache.remember_snapshot('US',{**snapshot(),flag:True}) is False


def test_live_success_and_fresh_store_recovery_use_separate_objects(monkeypatch):
    records={}
    def save(market,payload):records[market]=copy.deepcopy(payload);return True
    def load(market):return copy.deepcopy(records.get(market))
    monkeypatch.setattr(cache,'snapshot_store',lambda:SimpleNamespace(save=save,load=load))
    payload=snapshot();assert cache.remember_snapshot('US',payload)
    payload['rows'][0]['price']=1
    assert cache.restore_snapshot('US')['rows'][0]['price']==100


@pytest.mark.parametrize('failure',['expired','future','currency','nonstock','duplicate','missing_quote','invalid_metric'])
def test_invalid_durable_snapshot_cannot_bypass_validation(monkeypatch,failure):
    payload=snapshot()
    if failure=='expired':payload['generated_at']='2026-08-01T00:00:00Z'
    if failure=='future':payload['generated_at']='2099-01-01T00:00:00Z'
    if failure=='currency':payload['rows'][0]['currency']='HKD'
    if failure=='nonstock':
        for row in payload['rows']:row.update(instrument_type='etf',name='ETF基金')
    if failure=='duplicate':payload['rows'].append(copy.deepcopy(payload['rows'][0]))
    if failure=='missing_quote':payload['rows'][0]['quote_time']=None
    if failure=='invalid_metric':payload['rows'][0]['pe_ratio']=float('nan')
    monkeypatch.setattr(cache.requests,'post',lambda *a,**k:SimpleNamespace(status_code=200,json=lambda:payload))
    assert cache.CloudSnapshotStore('https://example.test','synthetic-key').load('US') is None


def test_write_does_not_mutate_live_payload_and_rejects_invalid_payload_before_network(monkeypatch):
    calls=[];monkeypatch.setattr(cache.requests,'post',lambda *a,**k:(calls.append(k) or SimpleNamespace(status_code=200,json=lambda:True)))
    payload=snapshot();before=copy.deepcopy(payload);store=cache.CloudSnapshotStore('https://example.test','synthetic-key')
    assert store.save('US',payload) is True and payload==before
    payload['rows'][0]['price']=0
    assert store.save('US',payload) is False and len(calls)==1


@pytest.mark.parametrize('failure',['network','http','json'])
def test_cache_failure_is_best_effort_and_contains_no_credential_text(monkeypatch,failure):
    def post(*args,**kwargs):
        if failure=='network':raise requests.ConnectionError('synthetic-secret')
        def content():raise ValueError('synthetic-secret')
        return SimpleNamespace(status_code=503 if failure=='http' else 200,json=content)
    monkeypatch.setattr(cache.requests,'post',post)
    store=cache.CloudSnapshotStore('https://example.test','synthetic-key')
    assert store.load('US') is None and store.save('US',snapshot()) is False


def test_local_or_missing_server_configuration_does_not_write_cloud_cache(monkeypatch):
    monkeypatch.delenv('VERCEL',raising=False)
    monkeypatch.setenv('SCREENER_JOB_BACKEND','supabase')
    assert cache.snapshot_store() is None
    monkeypatch.setenv('VERCEL','1');monkeypatch.delenv('SUPABASE_SERVICE_KEY',raising=False)
    assert cache.snapshot_store() is None
