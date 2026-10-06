import json
from datetime import datetime, timedelta, timezone

import pytest


def test_directory_excludes_non_equities_and_keeps_class_symbols():
    from investment.data.us_universe import parse_directory
    nasdaq = 'Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares\nAAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\nQQQ|Invesco ETF|Q|N|N|100|Y|N\nTEST|Test - Common Stock|Q|Y|N|100|N|N\nUNIT|Corp - Units|Q|N|N|100|N|N\nFile Creation Time: 1005202621:00|||||||'
    other = 'ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol\nBRK.B|Berkshire Hathaway Class B Common Stock|N|BRK.B|N|100|N|BRK/B\nXYZ.P|XYZ Preferred Stock|N|XYZp|N|100|N|XYZ.P\nADR|Company American Depositary Shares|A|ADR|N|100|N|ADR\nFile Creation Time: 1005202621:00|||||||'
    rows, stats = parse_directory(nasdaq, other)
    assert {r['ticker'] for r in rows} == {'AAPL', 'BRK.B', 'ADR'}
    assert {r['exchange'] for r in rows} == {'NASDAQ', 'NYSE', 'AMEX'}
    assert stats['listed_count'] == 7 and stats['eligible_count'] == 3


def test_filters_apply_before_history_and_missing_cap_cannot_match():
    from investment.data.us_universe import USFilters, filter_rows
    rows = [dict(ticker='BIG', price=10, market_cap=2e9, amount=2e6, exchange='NYSE'),
            dict(ticker='SMALL', price=10, market_cap=1e8, amount=2e6, exchange='NYSE'),
            dict(ticker='UNKNOWN', price=10, market_cap=None, amount=2e6, exchange='NYSE')]
    assert [r['ticker'] for r in filter_rows(rows, USFilters())] == ['BIG']
    assert len(filter_rows(rows, USFilters(min_market_cap=None, min_price=None, min_amount=None))) == 3
    assert filter_rows(rows, USFilters(exchange='NASDAQ')) == []


@pytest.mark.parametrize('values', [dict(min_market_cap=10, max_market_cap=1), dict(min_price=10, max_price=1), dict(min_amount=-1), dict(min_price=float('nan')), dict(exchange='OTC')])
def test_invalid_filter_ranges_are_rejected(values):
    from investment.data.us_universe import USFilters
    with pytest.raises(ValueError):
        USFilters(**values)


def snapshot():
    now = datetime.now(timezone.utc).isoformat()
    row = dict(ticker='AAPL', name='Apple Common Stock', market='US', currency='USD', exchange='NASDAQ', instrument_type='stock', classification_source='Nasdaq Trader official directory', price=200, amount=1e9, market_cap=3e12, quote_as_of=now)
    return dict(version='us-universe-v1', market='US', generated_at=now, directory_generated_at=now,
                source='Nasdaq Trader directory + Eastmoney US quotes', directory=[{k: row[k] for k in ('ticker','name','exchange','instrument_type','classification_source')}],
                directory_stats=dict(listed_count=1, eligible_count=1, excluded_count=0), rows=[row], quote_provider_total=1)


def test_snapshot_age_missing_quotes_and_identity_are_validated(tmp_path):
    from investment.data.us_universe import read_us_snapshot
    path = tmp_path / 'us.json'
    payload = snapshot()
    path.write_text(json.dumps(payload))
    scan = read_us_snapshot(path)
    assert scan['universe_count'] == 1 and scan['quote_coverage_count'] == 1
    payload['generated_at'] = (datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError): read_us_snapshot(path)
    payload = snapshot(); payload['rows'][0]['ticker'] = 'OTHER'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError): read_us_snapshot(path)


def test_incomplete_quote_pages_cannot_publish_as_complete():
    from investment.data.us_universe import validate_quote_pages
    with pytest.raises(ValueError):
        validate_quote_pages([{'total': 101, 'diff': [{'f12': 'AAPL', 'f13': 105}]}])


def test_tencent_us_quote_units_currency_and_identity():
    from investment.data.us_universe import parse_tencent_quotes
    fields = [''] * 66
    for index, value in {2:'AAPL.OQ',3:'200',6:'100',30:'2026-10-05 16:00:02',32:'1.5',35:'USD',37:'20000',39:'25',45:'30000'}.items():
        fields[index] = value
    identity = snapshot()['directory'][0]
    body = 'v_usAAPL="'+'~'.join(fields)+'";'
    rows = parse_tencent_quotes(body, {'AAPL': identity}, now=datetime(2026,10,6,tzinfo=timezone.utc))
    assert rows[0]['market_cap'] == 3e12 and rows[0]['amount'] == 20000 and rows[0]['volume'] == 100
    assert rows[0]['quote_as_of'] == '2026-10-05T16:00:02-04:00'
    assert parse_tencent_quotes(body.replace('USD','CNY'), {'AAPL': identity}) == []
    assert parse_tencent_quotes(body.replace('AAPL.OQ','MSFT.OQ'), {'AAPL': identity}) == []


def test_us_route_filters_before_enriching_and_exposes_coverage(monkeypatch):
    import asyncio
    from investment.api.routes import formula_ranking as route
    row = snapshot()['rows'][0]
    smaller = {**row, 'ticker': 'SMALL', 'market_cap': 1e8}
    monkeypatch.setattr(route, 'scan_foreign_market', lambda _: {**snapshot(), 'rows': [row, smaller], 'universe_count': 5000, 'quote_coverage_count': 4800, 'quote_missing_count': 200})
    captured = []
    monkeypatch.setattr(route, 'enrich_foreign_history', lambda rows, **kw: captured.extend(rows) or rows)
    result = asyncio.run(route.formula_ranking('US', 20, 'balanced'))['result']
    assert [r['ticker'] for r in captured] == ['AAPL']
    assert result['universe_count'] == 5000 and result['filtered_count'] == 1
    assert result['scanned_count'] == 4800 and result['scoring_limit'] == 120
    assert result['quote_missing_count'] == 200


def test_us_unavailable_does_not_silently_return_legacy_98(monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from investment.api.routes import formula_ranking as route
    monkeypatch.setattr(route, 'scan_foreign_market', lambda _: (_ for _ in ()).throw(ValueError('expired')))
    with pytest.raises(HTTPException) as error:
        asyncio.run(route.formula_ranking('US', 20, 'balanced'))
    assert error.value.status_code == 503


def test_ai_us_filters_full_quote_pool_but_bounds_history_work(monkeypatch):
    from investment.api.routes import ai_screener as route
    rows = [{**snapshot()['rows'][0], 'ticker': f'STOCK{i}', 'amount': i+1} for i in range(300)]
    monkeypatch.setattr(route, 'scan_foreign_market', lambda _: {'rows': rows, 'universe_count': 5000, 'quote_missing_count': 200})
    selected = []
    monkeypatch.setattr(route, 'enrich_screen_history', lambda rows, *args: selected.extend(rows) or rows)
    plan = route.ScreenPlan(summary='market cap', filters=[route.Condition(field='market_cap', op='gte', value=1e9)])
    result = route.execute(plan, 20, 'US')
    assert len(selected) == 120 and selected[0]['ticker'] == 'STOCK299'
    assert result['snapshot_matched_count'] == 300 and result['history_deferred_count'] == 180
    assert result['universe_count'] == 5000
    assert '120' in result['ranking_note'] and '全部补齐' not in result['ranking_note']
