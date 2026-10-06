"""Validate sealed US reference research summaries without reading historical archives."""
import hashlib
import json
import math
from pathlib import Path


def require(value):
    if not value: raise ValueError('Invalid US cover research summary')


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def read_summary(root):
    folder=Path(root)/'api/research_reports_us_cover'
    raw=(folder/'summary.json').read_bytes();seal=json.loads((folder/'seal.json').read_bytes())
    require(hashlib.sha256(raw).hexdigest()==seal['summary_sha256']);data=json.loads(raw)
    require(data['schema']=='us-cover-research-summary-v1' and data['status']=='research_only' and
        data['market']=='US' and data['applied'] is False and data['historical_mapping_complete'] is False)
    require((data['requested_count'],data['available_count'],data['download_failure_count'],data['excluded_fund_count'])==(60,56,3,1))
    require((data['train_days'],data['test_days'],data['fold_count'])==(240,80,5) and data['one_way_cost']==.0015)
    require(data['supplemented_tickers']==['BG','CARR','IOSP','MNRO'])
    require(data['test_start']=='2024-12-09' and data['test_end']=='2026-07-16')
    require(data['execution']=={'market':'US','initial_capital':10000,'minimum_fee':1,'entry_lot_size':1})
    coverage=data['coverage'];require(coverage['denominator']==1120)
    for field in ('market_cap','pe_ratio','pb_ratio'):
        require(all(type(coverage[field][arm]) is int and 0<=coverage[field][arm]<=1120 for arm in ('before','after')))
    require(coverage['market_cap']['after']>=coverage['market_cap']['before'])
    require(all(coverage[f]['before']==coverage[f]['after'] for f in ('pe_ratio','pb_ratio')))
    require([row['mode'] for row in data['modes']]==['balanced','conservative','aggressive'])
    for row in data['modes']:
        require(len(row['report_sha256'])==64)
        require([r['one_way_cost'] for r in row['cost_stress']]==[.003,.005])
        for metrics in [row['before'],row['after'],*row['cost_stress']]:
            require(all(finite(metrics[k]) for k in ('net_return','max_drawdown','average_exposure')) and metrics['net_return']>=-1
                and 0<=metrics['max_drawdown']<=1 and 0<=metrics['average_exposure']<=1 and metrics['days']==400)
    return data
