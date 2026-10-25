"""Build exact-universe selected-policy snapshot; optionally refresh verified raw data."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from data import cn_real_data as real
from data.selected_momentum import POLICY, market_gate

ROOT=Path(__file__).resolve().parents[1]
BASE=real.BASE
OUT=ROOT/'api/research_reports/momentum-selected.json'
UNIVERSE=ROOT/'api/research_reports/momentum-universe.json'


def ranked_rows(panel, as_of, universe):
    """Same float32 ret12 and ATR eligibility as the original weekly panel."""
    parts=[]
    cutoff=pd.Timestamp(as_of)
    for code, group in panel[panel['date']<=cutoff].groupby('code',sort=False):
        if code not in universe:continue
        w=group.sort_values('date').set_index('date').resample('W-FRI').agg(
            close=('close','last'),high=('high','max'),low=('low','min')).dropna()
        w=w[w.index<=cutoff]
        if len(w)<40:continue
        close=w['close'];prev=close.shift(1)
        atr=pd.concat([w.high-w.low,(w.high-prev).abs(),(w.low-prev).abs()],axis=1).max(axis=1).rolling(14).mean()/close
        ret=(close/close.shift(12)-1).astype('float32')
        if w.index[-1]!=cutoff or not np.isfinite(ret.iloc[-1]) or not np.isfinite(np.float32(atr.iloc[-1])):continue
        parts.append(dict(ticker=code,name=universe[code],momentum_pct=float(ret.iloc[-1])*100,
                          signal_close_hfq=float(close.iloc[-1]),price_basis='hfq_not_executable'))
    # Original panel groups by sorted stock code; stable ret12 ordering preserves ties.
    parts.sort(key=lambda r:-r['momentum_pct'])
    return [dict(row,rank=i+1) for i,row in enumerate(parts)]


def build(refresh=False):
    now=datetime.now(timezone(timedelta(hours=8)))
    if refresh:
        frozen=json.loads(UNIVERSE.read_text(encoding='utf-8'))
        universe=frozen['universe'];end=now.date().isoformat()
        start=(now.date()-timedelta(days=730)).isoformat()
        run=ROOT/'storage/stock_picker/research/selected-momentum-refresh'/now.strftime('%Y%m%dT%H%M%S')
        frames=[]
        for code in universe:
            fetched=real.tencent_daily(run,code,start,end,'hfq')
            audit=real.validate_bars(fetched['bars'])
            if not audit['ok']:raise ValueError(f'invalid_history:{code}')
            rows=fetched['bars']
            frames.append(pd.DataFrame(rows).assign(code=code))
        panel=pd.concat(frames,ignore_index=True);panel['date']=pd.to_datetime(panel['date'])
        market=real.csindex_perf(run,'000300',start,end)['bars']
        provenance=dict(universe_sha256=hashlib.sha256(UNIVERSE.read_bytes()).hexdigest(),refresh_archive=str(run.relative_to(ROOT)))
    else:
        d=json.loads((BASE/'dataset.json').read_text(encoding='utf-8'))
        universe={code:meta['name'] for code,meta in d['targets'].items()
                  if meta['kind']=='stock' and meta['status']=='ok' and meta['rows']>=300}
        assert len(universe)==793
        real.write_atomic(UNIVERSE,dict(universe=universe,frozen_at=now.isoformat(),bias='Current surviving constituents, not PIT'))
        panel=pd.read_parquet(BASE/'training/panel.parquet')
        market=real.load_bars(BASE,'000300')
        provenance={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest()
                    for name in ['dataset.json','training/panel.parquet','cs-signal-separation-r2.json']}
    market=[r for r in market if r['date']<=now.date().isoformat()]
    market_day=market[-1]['date']
    friday=pd.Timestamp(market_day).to_period('W-FRI').end_time.normalize()
    if friday>pd.Timestamp(market_day):friday-=pd.Timedelta(days=7)
    # Never publish an incomplete current W-FRI bucket as completed.
    signal_day=friday.strftime('%Y-%m-%d')
    ranks=ranked_rows(panel,signal_day,universe)
    if len(ranks)<700:raise ValueError('insufficient_ranking_coverage')
    latest={r['ticker']:r for r in ranks[:40]}
    quotes={}
    run=ROOT/'storage/stock_picker/research/selected-momentum-quotes'/now.strftime('%Y%m%dT%H%M%S')
    for code in latest:
        try:
            bars,raw,meta=real.tencent_window(code,market_day,market_day,'')
            real.archive(run,code,'native',raw,meta)
            valid=[b for b in bars if b['date']==market_day]
            if valid:
                quotes[code]=dict(price=valid[-1]['close'],as_of=market_day,price_basis='unadjusted',source_sha256=hashlib.sha256(raw).hexdigest())
        except Exception:pass  # Missing raw quote blocks sizing, never use hfq as execution price.
    gate=market_gate([r['close'] for r in market]);gate['as_of']=market_day
    results=json.loads((BASE/'cs-signal-separation-r2.json').read_text(encoding='utf-8')) if not refresh else json.loads(OUT.read_text(encoding='utf-8'))['backtest']
    if not refresh:results={k:results[k] for k in ['stocks','costs','results']}
    report=dict(version=POLICY['version'],active_policy=True,mode='decision_support',automation_enabled=False,
                generated_at=now.isoformat(),signal_as_of=signal_day,market=gate,policy=POLICY,
                universe_size=len(universe),ranked_count=len(ranks),candidates=[dict(r,native_quote=quotes.get(r['ticker'])) for r in ranks[:40]],
                backtest=results,provenance=provenance,
                limitations=['793只当前成分样本有幸存者偏差，非历史时点股票池。',
                '527.879%是已观察历史的研究收益，复权执行、历史限价、真实税费和公司行动仍有简化。',
                '每周信号仅补空位，不按排名淘汰未到期持仓，不在周中补位。',
                '市场弱时停止新增，不因跌破MA120自动清空已有持仓。',
                '原程序持有计数20在递增前检查，通常是买入后第21个有报价交易日收盘退出；不悄悄改成第20日。',
                '当前候选不是历史回测期末持仓；回测期末清算是统计处理，不是每周强制清仓。'])
    real.write_atomic(OUT,report)
    print(json.dumps(dict(signal=signal_day,market=gate,candidates=len(ranks),native_quotes=len(quotes)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true')
    build(parser.parse_args().refresh)
