import pytest
from investment.data import cn_live_scanner as cn, foreign_live_scanner as foreign


def unavailable(*args):raise RuntimeError('provider offline')


@pytest.mark.parametrize('market',['HK','US'])
def test_provider_outage_uses_durable_snapshot_before_packaged_hk(monkeypatch,market):
    snapshot={'rows':[{'ticker':'test','price':10}],'cached':True,'generated_at':'original'}
    monkeypatch.setattr(foreign.base,'scan_foreign_market',unavailable)
    monkeypatch.setattr(foreign,'restore_snapshot',lambda requested:snapshot if requested==market else None)
    monkeypatch.setattr(foreign,'read_hk_snapshot',lambda:pytest.fail('云端成功后不能再读较旧打包数据'))
    assert foreign.scan_foreign_market(market) is snapshot


def test_cn_outage_preserves_full_durable_universe(monkeypatch):
    snapshot={'rows':[{'ticker':str(i)} for i in range(2500)],'generated_at':'original','cached':True}
    monkeypatch.setattr(cn.base,'scan_cn_market',unavailable);monkeypatch.setattr(cn,'scan_sina_market',unavailable)
    monkeypatch.setattr(cn,'restore_snapshot',lambda market:snapshot)
    monkeypatch.setattr(cn,'read_saved_snapshot',lambda:pytest.fail('完整云端缓存成功后不能降级'))
    assert cn.scan_cn_market() is snapshot


def test_live_sina_is_remembered_without_changing_original_dates(monkeypatch):
    snapshot={'rows':[{'ticker':str(i)} for i in range(2500)],'generated_at':'original'}
    monkeypatch.setattr(cn.base,'scan_cn_market',unavailable);monkeypatch.setattr(cn,'scan_sina_market',lambda:snapshot)
    called=[];monkeypatch.setattr(cn,'remember_snapshot',lambda market,payload:called.append((market,payload)))
    assert cn.scan_cn_market() is snapshot and called==[('CN',snapshot)]


def test_us_missing_durable_cache_preserves_provider_failure(monkeypatch):
    monkeypatch.setattr(foreign.base,'scan_foreign_market',unavailable)
    monkeypatch.setattr(foreign,'restore_snapshot',lambda market:None)
    with pytest.raises(RuntimeError,match='provider offline'):foreign.scan_foreign_market('US')
