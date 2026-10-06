import asyncio
import pytest
from investment.api.routes import formula_ranking as api
from investment.data import foreign_live_scanner as live
from investment.data import hot_stocks
from investment.data import cn_live_scanner as cn


@pytest.mark.parametrize('market', ['HK', 'US'])
def test_ranking_recovers_durable_candidates_after_provider_failure(monkeypatch, tmp_path, market):
    assert api.scan_foreign_market is live.scan_foreign_market
    def unavailable(*args, **kwargs):
        raise RuntimeError('provider unavailable')
    rows = [{'ticker': f'hk{i+1:05d}' if market == 'HK' else 'STOCK' + chr(65+i),
             'market': market, 'currency': 'HKD' if market == 'HK' else 'USD',
             'name': 'ordinary share', 'price': 10, 'amount': 1000000,
             'pe_ratio': 20, 'pb_ratio': 2, 'market_cap': 1000000000,
             'quote_as_of': None} for i in range(20)]
    snapshot = {'market': market, 'generated_at': '2026-10-02T20:00:00+00:00',
                'rows': rows, 'source': 'validated durable snapshot', 'cached': True, 'stale': True}
    restored = []
    monkeypatch.setattr(live.base, 'scan_foreign_market', unavailable)
    monkeypatch.setattr(live, 'restore_snapshot', lambda region: restored.append(region) or snapshot)
    monkeypatch.setattr(api, 'enrich_foreign_history', lambda values, **kwargs: values)
    monkeypatch.setattr(api, '_latest_result', lambda: {})
    result = asyncio.run(api.formula_ranking(market, 20, 'balanced'))['result']
    assert len(result['items']) == 20
    assert restored == [market]
    assert result['source'] == snapshot['source']
    assert result['generated_at'] == snapshot['generated_at']
    assert result['cached'] is True and result['snapshot_only'] is True
    assert result['items'][0]['quote_as_of'] is None


def test_combined_ranking_propagates_snapshot_age_and_market_source(monkeypatch):
    row = {'ticker': 'hk00700', 'market': 'HK', 'price': 10, 'amount': 1000000}
    monkeypatch.setattr(api, 'scan_foreign_market', lambda market: {'rows': [row] if market == 'HK' else [],
        'generated_at': '2026-10-02T20:00:00+00:00', 'source': market + ' durable', 'cached': True, 'stale': True})
    monkeypatch.setattr(api, 'scan_cn_market', lambda: {'rows': [], 'generated_at': None, 'cached': False})
    monkeypatch.setattr(api, 'enrich_foreign_history', lambda values, **kwargs: values)
    monkeypatch.setattr(api, 'enrich_stock_history', lambda values, **kwargs: values)
    result = asyncio.run(api.formula_ranking('all', 20, 'balanced'))['result']
    assert result['snapshot_only'] is True
    hk = next(source for source in result['market_sources'] if source['market'] == 'HK')
    assert hk['generated_at'] == '2026-10-02T20:00:00+00:00' and hk['snapshot_only'] is True


def test_cn_ranking_recovers_full_durable_universe_and_marks_snapshot(monkeypatch):
    assert api.scan_cn_market is cn.scan_cn_market
    def unavailable(*args, **kwargs):
        raise RuntimeError('provider unavailable')
    rows = [{'ticker': f'sh{600+i//1000:03d}{i%1000:03d}' if i < 2000 else f'sh603{i%1000:03d}', 'market': 'CN', 'price': 10, 'amount': 1000000,
             'quote_as_of': '2026-09-30T15:00:00+08:00'} for i in range(2500)]
    snapshot = {'rows': rows, 'generated_at': '2026-09-30T15:00:00+08:00',
                'cached': True, 'stale': True, 'source': 'validated CN durable snapshot'}
    monkeypatch.setattr(cn.base, 'scan_cn_market', unavailable)
    monkeypatch.setattr(cn, 'scan_sina_market', unavailable)
    monkeypatch.setattr(cn, 'restore_snapshot', lambda market: snapshot)
    monkeypatch.setattr(cn, 'remember_snapshot', lambda *args: None)
    monkeypatch.setattr(api, 'enrich_stock_history', lambda values, **kwargs: values[:120])
    monkeypatch.setattr(api, '_latest_result', lambda: {})
    result = asyncio.run(api.formula_ranking('CN', 20, 'balanced'))['result']
    assert result['scanned_count'] == 2500 and len(result['items']) == 20
    assert result['snapshot_only'] is True and result['cached'] is True
    assert result['generated_at'] == snapshot['generated_at']
