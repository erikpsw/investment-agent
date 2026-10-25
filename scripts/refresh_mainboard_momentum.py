"""Refresh the mainboard snapshot; archived simulation charts stay immutable."""
import hashlib,json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pandas as pd
from data import cn_real_data as real
from data.full_cn_scope import classify_equity
from data.selected_momentum import market_gate
from scripts.build_selected_momentum import ranked_rows

ROOT=Path(__file__).resolve().parents[1]


def main():
    now=datetime.now(timezone(timedelta(hours=8)));end=now.date().isoformat();start=(now.date()-timedelta(days=720)).isoformat()
    out=ROOT/'api/research_reports/momentum-mainboard.json';old=json.loads(out.read_text(encoding='utf-8'))
    universe=json.loads((out.parent/'momentum-mainboard-universe.json').read_text(encoding='utf-8'))['universe']
    run=ROOT/'storage/stock_picker/research/mainboard-momentum-refresh'/now.strftime('%Y%m%dT%H%M%S')
    market=real.csindex_perf(run,'000300',start,end)['bars'];day=market[-1]['date']
    friday=pd.Timestamp(day).to_period('W-FRI').end_time.normalize()
    if friday>pd.Timestamp(day):friday-=pd.Timedelta(days=7)
    signal=friday.strftime('%Y-%m-%d')
    def one(item):
        code,name=item
        if classify_equity(dict(ticker=code,name=name))!='eligible':return [],'st_or_delisting'
        bars,raw,meta=real.tencent_window(code,start,end,'hfq');real.archive(run,code,'history',raw,meta)
        if len(bars)>=640 or not real.validate_bars(bars)['ok']:raise ValueError(f'invalid_history:{code}')
        if not bars:raise ValueError(f'empty_history:{code}')
        frame=pd.DataFrame(bars);frame['date']=pd.to_datetime(frame['date']);frame['code']=code
        r=ranked_rows(frame,signal,{code:name})
        return r,('ok' if r else 'insufficient_or_stale_history')
    ranks=[];counts=Counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rows,status in pool.map(one,universe.items()):ranks.extend(rows);counts[status]+=1
    if len(ranks)<len(universe)*.8:raise ValueError('ranking_coverage_too_low')
    ranks.sort(key=lambda r:(-r['momentum_pct'],r['ticker']))
    for i,r in enumerate(ranks):r['rank']=i+1
    quotes={}
    for r in ranks[:40]:
        code=r['ticker']
        try:
            bars,raw,meta=real.tencent_window(code,day,day,'');real.archive(run,code,'native',raw,meta)
            if bars and bars[-1]['date']==day:quotes[code]=dict(price=bars[-1]['close'],as_of=day,price_basis='unadjusted',source_sha256=hashlib.sha256(raw).hexdigest())
        except Exception:pass
    gate=market_gate([r['close'] for r in market]);gate['as_of']=day
    report=dict(old,generated_at=now.isoformat(),signal_as_of=signal,market=gate,ranked_count=len(ranks),
        _rankings=ranks,candidates=[dict(r,native_quote=quotes.get(r['ticker'])) for r in ranks[:40]],coverage=dict(counts))
    real.write_atomic(out,report)
    print(json.dumps(dict(signal=signal,ranked=len(ranks),coverage=dict(counts))))


if __name__=='__main__':main()
