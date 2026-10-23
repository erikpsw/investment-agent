"""Verify a reviewed deployment using an isolated, immediately removed test identity.
Tokens stay in memory and curl stdin; fixtures are never attributed to a human user.
"""
import argparse
import json
from pathlib import Path
import shutil
import time
import subprocess
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlparse
import requests
from dotenv import dotenv_values
from investment.data.pat_store import SupabasePersonalAccessTokenStore
from investment.data.portfolio_store import SupabasePortfolioStore
from investment.data.score_tracking_store import SupabaseScoreTrackingStore

parser=argparse.ArgumentParser()
parser.add_argument('origin')
parser.add_argument('--protected',action='store_true')
args=parser.parse_args()
assert args.origin in ('https://investment-agent-rcfs6hcad-erikpans-projects.vercel.app','https://www.erikai.top')
values=dotenv_values('.env')
assert urlparse(values['SUPABASE_URL']).hostname=='rtivvccdqnwspbcfrrno.supabase.co'
portfolio=SupabasePortfolioStore(values['SUPABASE_URL'],values.get('SUPABASE_SERVICE_KEY') or values.get('SUPABASE_SERVICE_ROLE_KEY'))
client=portfolio._client
pat=SupabasePersonalAccessTokenStore(values['SUPABASE_URL'],values.get('SUPABASE_SERVICE_KEY') or values.get('SUPABASE_SERVICE_ROLE_KEY'),client=client)
store=SupabaseScoreTrackingStore(client)
owner='deployment-smoke-'+str(uuid4())
created=None
checks=[]
live_detection={}
cli=Path.home()/'AppData/Roaming/npm/node_modules/vercel/dist/vc.js'

def request(method,path,body=None,auth=True,expected=200):
    token=created.token if auth and created else None
    safe_retry=method=='GET' or (body is not None and 'request_id' in body) or path.endswith('/risk-settings')
    if args.protected:
        config=['silent','show-error','max-time = 70','write-out = "\\n%{http_code}"', 'request = '+json.dumps(method)]
        if token: config.append('header = '+json.dumps('Authorization: Bearer '+token))
        if body is not None:
            config.extend(['header = "Content-Type: application/json"','data = '+json.dumps(json.dumps(body))])
        safe_retry=method=='GET' or (body is not None and 'request_id' in body) or path.endswith('/risk-settings')
        for attempt in range(3 if safe_retry else 1):
            completed=subprocess.run([shutil.which('node'),str(cli),'curl',path,'--deployment',args.origin,'--','--config','-'],input='\n'.join(config)+'\n',capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=100)
            raw,separator,status_text=completed.stdout.rpartition('\n')
            status=int(status_text.strip()) if status_text.strip().isdigit() else 0
            if status: break
            if attempt<2 and safe_retry: time.sleep(1)
        if not status: raise RuntimeError(f'curl transport failed for {method} {path}; exit={completed.returncode}')
        try: payload=json.loads(raw)
        except ValueError: payload={}
    else:
        for attempt in range(3 if safe_retry else 1):
            try:
                r=requests.request(method,args.origin+path,json=body,headers={'Authorization':'Bearer '+token} if token else {},timeout=70,allow_redirects=False)
                if r.status_code in (502,503,504) and safe_retry and attempt<2:
                    time.sleep(1);continue
                break
            except requests.RequestException:
                if not safe_retry or attempt==2: raise
                time.sleep(1)
        status=r.status_code
        try: payload=r.json()
        except ValueError: payload={}
    if status!=expected:
        raise AssertionError(f'{method} {path}: {status}, expected {expected}; '+str(payload.get('detail',''))[:180])
    checks.append({'method':method,'path':path,'status':status})
    print(f'PASS {method} {path} {status}',flush=True)
    return payload.get('result',payload)

try:
    request('GET','/health',auth=False)
    request('GET','/api/portfolio/risk-overview',auth=False,expected=401)
    created=pat.create(owner,'Temporary deployment verification')
    state=request('GET','/api/portfolio/risk-overview')
    assert state['items']==[] and state['revision']==0
    assert request('GET','/api/securities/US/AAPL/score-history?trading_days=90')['items']==[]
    request('PUT','/api/portfolio/risk-settings',{'mode':'balanced'},expected=403)
    # Write scopes belong only to this synthetic test identity and are removed in finally.
    client.table(pat.TABLE).update({'scopes':['portfolio:read','portfolio:write']}).eq('user_id',owner).eq('id',created.record.id).execute()
    request('PUT','/api/portfolio/risk-settings',{**state['settings'],'mode':'balanced','total_risk_percent':5})
    cash={'action':'set_cash','currency':'USD','amount':1000,'request_id':str(uuid4()),'expected_revision':0}
    assert request('POST','/api/portfolio/transactions',cash)['revision']==1
    stamp=datetime.now(timezone.utc).isoformat()
    snapshot=store.append_snapshot(owner,{'market':'US','ticker':'AAPL','mode':'balanced','formula_version':'formula-v2','config_fingerprint':'deployment-fixture',
        'quote_as_of':stamp,'observed_at':stamp,'formula_score':75,'data_coverage':1,'price':100,'price_basis':'raw','quality_status':'ok','source':'isolated deployment fixture'})['snapshot']
    buy={'action':'buy','market':'US','instrument_id':'AAPL','quantity':2,'price':100,'fee':1,'request_id':str(uuid4()),'expected_revision':1,'executed_at':datetime.now(timezone.utc).isoformat(),'score_snapshot_id':snapshot['id']}
    bought=request('POST','/api/portfolio/transactions',buy)
    assert bought['management']['US:AAPL']['entry_snapshot']['formula_score']==75
    assert request('POST','/api/portfolio/transactions',buy)['revision']==2
    plan={'snapshot_id':snapshot['id'],'config_fingerprint':'deployment-fixture','quote_as_of':stamp,'currency':'USD','price_basis':'raw','reference_price':100,'stop_loss':95,'take_profit_1':110,'take_profit_2':115}
    request('PUT','/api/portfolio/positions/US/AAPL/protection',{'episode_id':bought['management']['US:AAPL']['episode_id'],'expected_revision':2,'plan':plan})
    current=request('GET','/api/portfolio/risk-overview')
    assert current['revision']==3 and current['items'][0]['planned_risk_native']==10
    assert current['items'][0]['detection']['change']['entry_delta']==0
    sold=request('POST','/api/portfolio/transactions',{'action':'sell','market':'US','instrument_id':'AAPL','quantity':2,'price':100,'request_id':str(uuid4()),'expected_revision':3})
    assert not sold['management']
    reentered=request('POST','/api/portfolio/transactions',{'action':'buy','market':'US','instrument_id':'AAPL','quantity':1,'price':100,'request_id':str(uuid4()),'expected_revision':4})
    assert reentered['management']['US:AAPL']['entry_snapshot'] is None
    request('POST','/api/portfolio/transactions',{**cash,'request_id':str(uuid4())},expected=409)
    history=request('GET','/api/securities/US/AAPL/score-history?trading_days=30')
    assert len(history['items'])==1
    client.table('user_watchlists').upsert({'user_id':owner,'groups':[{'id':'deployment-cn','name':'Deployment check','items':[{'market':'CN','ticker':'sh600519'}]}]},on_conflict='user_id').execute()
    detected=request('POST','/api/watchlists/detection',{'securities':[{'market':'US','ticker':'AAPL'},{'market':'CN','ticker':'sh600519'}],'mode':'balanced','request_id':str(uuid4())})
    item=detected['items'][0]
    assert item['market']=='US' and item['ticker']=='AAPL' and item['status'] in ('ok','unavailable')
    live_detection=[{'market':row['market'],'ticker':row['ticker'],'status':row['status'],'saved':bool(row.get('saved')),'quality_status':row.get('snapshot',{}).get('quality_status')} for row in detected['items']]
    print('LIVE_DETECTION '+json.dumps(live_detection),flush=True)
finally:
    # Delete the isolated token first, then test records; retry transport failures without masking cleanup.
    for table in ['user_personal_access_tokens','user_position_events','user_position_management','user_security_score_snapshots','user_portfolio_risk_settings','user_watchlists','user_portfolios']:
        for attempt in range(3):
            try:
                cleaned=requests.delete(values['SUPABASE_URL']+'/rest/v1/'+table,params={'user_id':'eq.'+owner},headers={'apikey':values.get('SUPABASE_SERVICE_KEY') or values.get('SUPABASE_SERVICE_ROLE_KEY'),'Authorization':'Bearer '+(values.get('SUPABASE_SERVICE_KEY') or values.get('SUPABASE_SERVICE_ROLE_KEY'))},timeout=20)
                cleaned.raise_for_status()
                break
            except requests.RequestException:
                if attempt==2: raise RuntimeError('Isolated test cleanup incomplete: '+table) from None
                time.sleep(1)

report={'origin':args.origin,'checks':checks,'passed':len(checks),'fixtures':'synthetic identity and accounting score; all removed','live_detection':live_detection,'cleanup':'completed'}
Path('docs/score-management-'+('staged' if args.protected else 'production')+'-checks-20261022.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
