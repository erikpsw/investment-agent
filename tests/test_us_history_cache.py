from investment.data.us_history_cache import apply_cached_history


def test_cache_never_replaces_current_quotes_or_uses_future_history():
    rows = [{'ticker': 'ABC', 'market': 'US', 'price': 20, 'quote_as_of': '2026-10-14T20:00:00-04:00'}]
    cached = {'ABC': {'history_as_of': '2026-10-14', 'change_5d': 3, 'price': 999}}
    result = apply_cached_history(rows, cached)[0]
    assert result['price'] == 20 and result['change_5d'] == 3
    cached['ABC']['history_as_of'] = '2026-10-15'
    assert 'change_5d' not in apply_cached_history(rows, cached)[0]


def test_missing_or_expired_history_is_reported():
    rows = [{'ticker': 'ABC', 'market': 'US', 'quote_as_of': '2026-10-14T20:00:00-04:00'}]
    assert apply_cached_history(rows, {})[0]['history_cache_missing']
    assert apply_cached_history(rows, {'ABC': {'history_as_of': '2026-09-01'}})[0]['history_cache_missing']
    assert apply_cached_history([{'ticker': 'ABC', 'market': 'US'}],
                                {'ABC': {'history_as_of': '2026-10-14'}})[0]['history_cache_missing']


def test_all_matching_scoring_never_launches_unbounded_network_requests(monkeypatch):
    import asyncio
    from investment.api.routes import formula_ranking as route
    rows = [{'ticker': f'STOCK{i}', 'market': 'US', 'price': 10, 'amount': i + 10000000,
             'market_cap': 2e9, 'quote_as_of': '2026-10-14T20:00:00-04:00'} for i in range(350)]
    monkeypatch.setattr(route, 'scan_foreign_market', lambda _: {'rows': rows, 'quote_coverage_count': 350})
    monkeypatch.setattr(route, 'enrich_foreign_history', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network work')))
    result = asyncio.run(route.formula_ranking('US', 20, 'balanced', scoring_limit=0))['result']
    assert result['candidate_count'] == 350 and result['filtered_count'] == 350
    assert result['scoring_limit'] == 0 and result['history_cache_missing_count'] == 350
    assert len(result['items']) == 20
    result = asyncio.run(route.formula_ranking('US', 20, 'balanced', scoring_limit=300))['result']
    assert result['candidate_count'] == 300


def test_invalid_scoring_limit_rejected_before_loading_market(monkeypatch):
    import asyncio
    import pytest
    from fastapi import HTTPException
    from investment.api.routes import formula_ranking as route
    monkeypatch.setattr(route, 'scan_foreign_market', lambda _: (_ for _ in ()).throw(AssertionError('scan')))
    with pytest.raises(HTTPException) as error:
        asyncio.run(route.formula_ranking('US', 20, 'balanced', scoring_limit=-1))
    assert error.value.status_code == 422


def test_default_scoring_reuses_valid_history_without_network(monkeypatch):
    import asyncio
    from investment.api.routes import formula_ranking as route
    from investment.data import us_history_cache as cache
    row = {'ticker': 'ABC', 'market': 'US', 'price': 10, 'amount': 2000000, 'market_cap': 2e9,
           'quote_as_of': '2026-10-14T20:00:00-04:00'}
    monkeypatch.setattr(route, 'scan_foreign_market', lambda _: {'rows': [row]})
    monkeypatch.setattr(cache, 'read_cache', lambda: {'ABC': {'history_as_of': '2026-10-14',
                        'change_5d': 1, 'change_20d': 2, 'change_60d': 3}})
    monkeypatch.setattr(route, 'enrich_foreign_history', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    result = asyncio.run(route.formula_ranking('US', 20, 'balanced'))['result']
    assert result['history_enriched_count'] == 1
    assert result['items'][0]['change_60d'] == 3


def test_worker_retains_good_factors_when_one_symbol_fails(monkeypatch, tmp_path):
    import json
    from scripts import refresh_us_history as worker
    path = tmp_path / 'history.json'
    monkeypatch.setattr(worker, 'PATH', path)
    old = {'OLD': {'history_as_of': '2026-10-12', 'change_5d': 1}}
    monkeypatch.setattr(worker, 'read_cache', lambda: old.copy())
    monkeypatch.setattr(worker, 'read_us_snapshot', lambda: {'rows': [{'ticker': 'OLD'}, {'ticker': 'NEW'}]})
    monkeypatch.setattr(worker, 'enrich_foreign_history', lambda *a, **k: [
        {'ticker': 'OLD', 'history_error': 'offline'},
        {'ticker': 'NEW', 'history_as_of': '2026-10-14', 'change_5d': 2, 'change_20d': 3, 'change_60d': 4}])
    worker.main()
    saved = json.loads(path.read_text())['items']
    assert saved['OLD'] == old['OLD']
    assert saved['NEW']['history_as_of'] == '2026-10-14'
    assert not path.with_suffix('.tmp').exists()
