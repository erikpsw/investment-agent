"""Compare AND pushdown with exhaustive history enrichment on synthetic facts."""
import copy
import itertools
from datetime import datetime, timedelta
import pytest
from investment.api.routes import ai_screener as api


def fixture_rows(market):
    return [{'ticker':f'T{i}','market':market,'name':'合成样本','price':100,
             'pe_ratio':pe,'market_cap':cap,'change_20d':99} for i,(pe,cap) in
            enumerate([(10,300),(30,300),(None,300),(10,50),(10,400),(10,500)])]


def synthetic_history(rows, market, as_of):
    result=[]
    for row in rows:
        clean={k:v for k,v in row.items() if k not in api.HISTORY_FIELDS}
        if row['ticker']!='T5':
            clean.update(change_5d=2,change_20d=10 if row['ticker']=='T4' else -5,
                         change_60d=20,history_as_of='2026-09-30',
                         risk_bars=[{'date':(datetime(2026,9,10)+timedelta(days=i)).date().isoformat(),
                                     'open':100,'high':102,'low':98,'close':100} for i in range(21)])
        result.append(clean)
    return result


@pytest.mark.parametrize('market',['CN','HK','US'])
@pytest.mark.parametrize('mode',['balanced','conservative','aggressive'])
@pytest.mark.parametrize('ordering',list(itertools.permutations(range(3))))
def test_and_pushdown_preserves_exhaustive_results_and_scores(monkeypatch,market,mode,ordering):
    rows=fixture_rows(market);before=copy.deepcopy(rows)
    scan={'rows':rows,'generated_at':'2026-09-30'}
    monkeypatch.setattr(api,'scan_cn_market',lambda:scan)
    monkeypatch.setattr(api,'scan_foreign_market',lambda _:scan)
    conditions=[api.Condition(field='pe_ratio',op='lt',value=20),
                api.Condition(field='market_cap',op='gte',value=100),
                api.Condition(field='change_20d',op='gt',value=0)]
    plan=api.ScreenPlan(summary='合成AND筛选',mode=mode,filters=[conditions[i] for i in ordering])
    exhaustive=[row for row in synthetic_history(rows,market,'2026-09-30')
                if all(api.match(row,condition) for condition in plan.filters)]
    expected=[api._rank_live_item(row,plan.mode) for row in exhaustive]
    calls=[]
    def enrich(values,market,as_of):
        calls.append([row['ticker'] for row in values])
        return synthetic_history(values,market,as_of)
    monkeypatch.setattr(api,'enrich_screen_history',enrich)
    result=api.execute(plan,1,market)
    assert calls==[['T0','T4','T5']]
    assert result['scanned_count']==6 and result['history_requested_count']==3
    assert result['history_prefiltered_count']==3
    assert result['history_enriched_count']==2 and result['history_failed_count']==1
    assert result['matched_count']==1 and result['items'][0]['ticker']=='T4'
    assert result['items'][0]['risk_plan']['status']=='ok'
    for key in ('formula_score','contributions','risk_plan','coverage','missing_factors'):
        if key in expected[0]: assert result['items'][0][key]==expected[0][key]
    assert result['filter_coverage']['pe_ratio']=={'available':5,'total':6}
    assert result['filter_coverage']['change_20d']=={'available':2,'total':3}
    assert '历史条件覆盖通过快照条件的候选' in result['ranking_note']
    assert rows==before


@pytest.mark.parametrize('market',['CN','HK','US'])
def test_no_snapshot_matches_skips_history_without_claiming_missing_metrics(monkeypatch,market):
    scan={'rows':fixture_rows(market),'generated_at':'2026-09-30'}
    monkeypatch.setattr(api,'scan_cn_market',lambda:scan);monkeypatch.setattr(api,'scan_foreign_market',lambda _:scan)
    def forbidden(*args,**kwargs):raise AssertionError('排除的股票不能补齐历史')
    monkeypatch.setattr(api,'enrich_screen_history',forbidden)
    plan=api.ScreenPlan(summary='无匹配',filters=[api.Condition(field='market_cap',op='gt',value=1000),api.Condition(field='change_20d',op='gt',value=0)])
    result=api.execute(plan,20,market)
    assert result['items']==[] and result['matched_count']==0 and result['scanned_count']==6
    assert result['history_requested_count']==result['history_failed_count']==0
    assert result['history_prefiltered_count']==6
    assert result['filter_coverage']['change_20d']=={'available':0,'total':0}


def test_pure_history_query_does_not_narrow_universe_or_use_snapshot_trend(monkeypatch):
    scan={'rows':fixture_rows('US'),'generated_at':'2026-09-30'}
    monkeypatch.setattr(api,'scan_foreign_market',lambda _:scan)
    called=[]
    def enrich(rows,market,as_of):called.append(len(rows));return synthetic_history(rows,market,as_of)
    monkeypatch.setattr(api,'enrich_screen_history',enrich)
    result=api.execute(api.ScreenPlan(summary='仅历史',filters=[api.Condition(field='change_20d',op='gt',value=0)]),1,'US')
    assert called==[6] and result['scanned_count']==6 and result['history_prefiltered_count']==0
    assert [item['ticker'] for item in result['items']]==['T4']
