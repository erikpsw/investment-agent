"""Read-only exchange directory acquisition, with HTTPS response archives."""
import hashlib
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path
import requests
import akshare as ak

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'storage/stock_picker/research/full-cn-momentum-20261025/directory'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    original=requests.sessions.Session.request
    counter=0
    def request(session,method,url,**kwargs):
        nonlocal counter
        if not url.startswith('https://') or kwargs.get('verify',True) is not True:
            raise ValueError('https_verified_requests_only')
        kwargs.setdefault('timeout',20)
        response=original(session,method,url,**kwargs)
        counter+=1;stem=OUT/f'response-{counter:04d}'
        stem.with_suffix('.raw').write_bytes(response.content)
        stem.with_suffix('.meta.json').write_text(json.dumps(dict(url=url,method=method,
            params=kwargs.get('params'),data=kwargs.get('data'),status=response.status_code,
            fetched_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(response.content).hexdigest()),ensure_ascii=False),encoding='utf-8')
        return response
    requests.sessions.Session.request=request
    tasks=[('sh_main',lambda:ak.stock_info_sh_name_code('主板A股'),'sh'),
           ('sh_star',lambda:ak.stock_info_sh_name_code('科创板'),'sh'),
           ('sz',lambda:ak.stock_info_sz_name_code('A股列表'),'sz'),
           ('bj',ak.stock_info_bj_name_code,'bj')]
    tasks_out=[];universe={}
    for name,fetch,prefix in tasks:
        try:
            frame=fetch()
            code_col='A股代码' if prefix=='sz' else '证券代码'
            name_col='A股简称' if prefix=='sz' else '证券简称'
            rows=[dict(ticker=prefix+str(row[code_col]).zfill(6),name=str(row[name_col]),exchange=prefix)
                  for row in frame.to_dict('records')]
            universe.update({r['ticker']:r for r in rows})
            result=dict(task=name,status='ok',rows=rows)
        except Exception as exc:result=dict(task=name,status='error',error=f'{type(exc).__name__}: {exc}')
        (OUT/f'{name}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        tasks_out.append(dict(task=name,status=result['status'],count=len(result.get('rows',[]))))
        print(json.dumps(tasks_out[-1]),flush=True)
    report=dict(acquired_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                complete=all(t['status']=='ok' for t in tasks_out),tasks=tasks_out,rows=list(universe.values()))
    (OUT/'directory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(complete=report['complete'],stocks=len(universe))),flush=True)


if __name__=='__main__':main()
