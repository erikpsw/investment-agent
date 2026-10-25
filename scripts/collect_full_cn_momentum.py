"""Resumable full-equity hfq histories; never hides unattempted or failed symbols."""
import hashlib,json,threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import pandas as pd
from data import cn_real_data as real
from data.full_cn_scope import classify_equity,coverage_ready

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'storage/stock_picker/research/full-cn-momentum-20261025'


def main():
    directory=json.loads((OUT/'directory/directory.json').read_text(encoding='utf-8'))
    (OUT/'tasks').mkdir(exist_ok=True);(OUT/'bars').mkdir(exist_ok=True)
    source=json.loads((real.BASE/'dataset.json').read_text(encoding='utf-8'))['targets']
    cutoff='2026-10-23';stop=threading.Event();failures=0;lock=threading.Lock()
    def one(row):
        nonlocal failures
        code=row['ticker'];task=OUT/'tasks'/f'{code}.json'
        scope_status=classify_equity(row)
        if scope_status=='excluded_board':
            result=dict(ticker=code,name=row['name'],status=scope_status,scope='mainboard')
            real.write_atomic(task,result)
            return result
        if task.exists():
            prior=json.loads(task.read_text(encoding='utf-8'))
            path=OUT/'bars'/f'{code}.json'
            if prior['status']=='ok' and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==prior['bars_sha256']:return prior
            if prior['status'] in ('st_or_delisting','not_equity','insufficient_history'):return prior
        status=classify_equity(row);result=dict(ticker=code,name=row['name'],status=status)
        if status=='eligible':
            if stop.is_set():return dict(result,status='pending')
            try:
                meta=source.get(code);origin='new_archive'
                if meta and meta.get('status')=='ok' and real.verify_bars_file(real.BASE,code)[0]:
                    bars=[b for b in real.load_bars(real.BASE,code) if '2024-01-01'<=b['date']<=cutoff]
                    origin='verified_reference_archive'
                else:
                    bars,raw,info=real.tencent_window(code,'2024-11-01',cutoff,'hfq')
                    real.archive(OUT,code,'hfq_2024',raw,info)
                    if len(bars)>=640:raise ValueError('window_truncated')
                if not bars:raise ValueError('no_verified_history')
                audit=real.validate_bars(bars)
                if not audit['ok']:raise ValueError(','.join(audit['errors']))
                path=OUT/'bars'/f'{code}.json';real.write_atomic(path,bars)
                weeks=pd.DataFrame(bars).assign(date=lambda f:pd.to_datetime(f.date)).set_index('date').close.resample('W-FRI').last().dropna()
                status='insufficient_history' if len(weeks)<40 else ('ok' if weeks.index[-1].strftime('%Y-%m-%d')==cutoff else 'suspended_or_stale')
                result.update(status=status,rows=len(bars),weeks=len(weeks),last_date=bars[-1]['date'],origin=origin,
                              bars_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                with lock:failures=0
            except Exception as exc:
                result.update(status='error',error=f'{type(exc).__name__}:{exc}')
                with lock:
                    failures+=1
                    if failures>=15:stop.set()
        real.write_atomic(task,result)
        return result
    results=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(one,row) for row in directory['rows']]
        for future in as_completed(futures):
            results.append(future.result())
            if len(results)%100==0:print(json.dumps(dict(done=len(results),counts=dict(Counter(r['status'] for r in results)))),flush=True)
    counts=dict(Counter(r['status'] for r in results))
    summary=dict(scope='mainboard',directory_complete=directory['complete'],directory_size=len(directory['rows']),as_of=cutoff,
                 counts=counts,ready=coverage_ready(directory['complete'],counts),records=sorted(results,key=lambda r:r['ticker']))
    real.write_atomic(OUT/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='records'}),flush=True)


if __name__=='__main__':main()
