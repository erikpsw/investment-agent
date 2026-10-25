"""Mainboard ranking plus original-basis archived per-stock simulation charts."""
import gzip,json,hashlib
from pathlib import Path
from collections import defaultdict
import pandas as pd
from data import cn_real_data as real
from data.momentum_visual import chart_payload
from scripts.build_selected_momentum import ranked_rows

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'storage/stock_picker/research/full-cn-momentum-20261025'
PUBLIC=ROOT/'web/public/strategy/momentum'


def build():
    summary=json.loads((DATA/'summary.json').read_text(encoding='utf-8'))
    if not summary['ready'] or summary['scope']!='mainboard':raise ValueError('mainboard_collection_incomplete')
    directory=json.loads((DATA/'directory/directory.json').read_text(encoding='utf-8'))
    names={r['ticker']:r['name'] for r in directory['rows']}
    reference=json.loads((ROOT/'api/research_reports/momentum-selected.json').read_text(encoding='utf-8'))
    frozen=json.loads((ROOT/'api/research_reports/momentum-universe.json').read_text(encoding='utf-8'))['universe']
    trades=json.loads((real.BASE/'trades-cs-signal-separation-r2.json').read_text(encoding='utf-8'))
    grouped=defaultdict(list)
    for t in trades:grouped[t['code']].append(t)
    assert len(trades)==1672
    PUBLIC.mkdir(parents=True,exist_ok=True)
    ranks=[];catalog=[];bytes_total=0
    for record in summary['records']:
        code=record['ticker'];status=record['status'];name=names[code]
        if status=='excluded_board' and code not in frozen:continue
        bars=[]
        if code in frozen:
            if not real.verify_bars_file(real.BASE,code)[0]:raise ValueError('invalid_reference_bars')
            bars=real.load_bars(real.BASE,code)
        elif (DATA/'bars'/f'{code}.json').exists():
            p=DATA/'bars'/f'{code}.json'
            if hashlib.sha256(p.read_bytes()).hexdigest()!=record.get('bars_sha256'):raise ValueError('bars_hash')
            bars=json.loads(p.read_text(encoding='utf-8'))
        if status=='ok':
            frame=pd.DataFrame(bars);frame['date']=pd.to_datetime(frame['date']);frame['code']=code
            ranks.extend(ranked_rows(frame,summary['as_of'],{code:name}))
        if bars:
            payload=chart_payload(code,name,bars,grouped[code])
            payload['eligibility']=status;payload['in_reference793']=code in frozen
            raw=json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            packed=gzip.compress(raw,mtime=0)
            (PUBLIC/f'{code}.json.gz').write_bytes(packed);bytes_total+=len(packed)
        catalog.append(dict(ticker=code,name=name,status=status,has_chart=bool(bars),in_reference793=code in frozen))
    ranks.sort(key=lambda r:(-r['momentum_pct'],r['ticker']))
    for i,r in enumerate(ranks):r['rank']=i+1
    main=dict(reference,scope='mainboard',scope_label='沪深主板',universe_size=sum(r['status']!='excluded_board' for r in summary['records']),
              ranked_count=len(ranks),candidates=[dict(r,native_quote=None) for r in ranks[:40]],
              backtest=dict(results=[],status='not_computed_for_mainboard'),coverage=summary['counts'],_rankings=ranks,
              limitations=['当前范围仅沪深主板，排除北交所、科创板、创业板、ST及退市标记。',
                           '主板范围改变了排名与交易，527.879%仅属于原793只历史对照；本范围收益未计算。']+reference['limitations'][2:])
    # Do not use adjusted chart values as native execution references.
    real.write_atomic(ROOT/'api/research_reports/momentum-mainboard.json',main)
    real.write_atomic(PUBLIC/'index.json',dict(default_scope='mainboard',as_of=summary['as_of'],coverage=summary['counts'],
         mainboard_rankings=ranks,catalog=catalog,reference_metrics=reference['backtest'],
         notes='Archived trades belong exclusively to the reference793 simulation, never actual user fills.'))
    print(json.dumps(dict(charts=sum(r['has_chart'] for r in catalog),ranked=len(ranks),compressed_bytes=bytes_total)),flush=True)


if __name__=='__main__':build()
