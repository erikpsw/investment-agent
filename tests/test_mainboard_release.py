import gzip,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_mainboard_has_no_reused_reference_returns_or_excluded_boards():
    report=json.loads((ROOT/'api/research_reports/momentum-mainboard.json').read_text(encoding='utf-8'))
    assert report['scope']=='mainboard'
    assert report['backtest']['results']==[]
    assert report['ranked_count']==len(report['_rankings'])
    assert report['ranked_count']>2900
    assert all(re.fullmatch(r'(?:sh60\d{4}|sz00\d{4})',r['ticker']) for r in report['_rankings'])
    assert all('ST' not in r['name'].upper() and '退' not in r['name'] for r in report['_rankings'])


def test_all_archived_trade_markers_retain_bar_dates_and_simulation_label():
    total=0
    folder=ROOT/'web/public/strategy/momentum'
    index=json.loads((folder/'index.json').read_text(encoding='utf-8'))
    for stock in index['catalog']:
        if not stock['has_chart']:continue
        payload=json.loads(gzip.decompress((folder/f"{stock['ticker']}.json.gz").read_bytes()))
        assert payload['series_kind']=='archived_research_not_actual_fills'
        assert payload['price_basis']=='hfq'
        dates={b[0] for b in payload['bars']}
        for trade in payload['trades']:
            assert payload['in_reference793']
            assert trade['entry_date'] in dates and trade['exit_date'] in dates
            total+=1
    assert total==1672
