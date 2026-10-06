"""Server-only job persistence through an atomic Supabase RPC."""
import re
import secrets
from urllib.parse import urlsplit
import requests


class CloudStoreUnavailable(RuntimeError):
    pass


class CloudJobStore:
    def __init__(self,url,key):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/') or not key:
            raise CloudStoreUnavailable('Cloud task storage is not configured')
        self.url=url.rstrip('/')+'/rest/v1/rpc/screener_job_rpc'
        self.headers={'apikey':key,'Authorization':'Bearer '+key,'Content-Type':'application/json'}

    def _rpc(self,operation,job_id,payload=None):
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}',job_id): raise ValueError('Invalid submission identifier')
        try:
            response=requests.post(self.url,headers=self.headers,json={'operation':operation,'job_id':job_id,'payload':payload},timeout=10)
            if response.status_code!=200: raise CloudStoreUnavailable('Cloud task storage unavailable')
            value=response.json()
        except (requests.RequestException,ValueError) as exc:
            raise CloudStoreUnavailable('Cloud task storage unavailable') from None
        if isinstance(value,dict) and value.get('error')=='capacity': raise RuntimeError('capacity')
        if isinstance(value,dict) and value.get('error')=='different request': raise ValueError('different request')
        if operation in ('heartbeat','finish','fail'):
            if not isinstance(value,bool): raise CloudStoreUnavailable('Invalid cloud task response')
        elif value is None and operation=='get': return None
        elif not isinstance(value,dict) or value.get('id')!=job_id or value.get('status') not in ('running','completed','failed','interrupted') or not isinstance(value.get('request'),dict) or (value.get('response') is not None and not isinstance(value['response'],dict)):
            raise CloudStoreUnavailable('Invalid cloud task response')
        return value

    def create(self,request,job_id=None):
        result=self._rpc('create',job_id or secrets.token_urlsafe(32),request)
        if not isinstance(result.get('created'),bool): raise CloudStoreUnavailable('Missing cloud task creation status')
        return result

    def get(self,job_id):
        result=self._rpc('get',job_id)
        if result is not None: result={k:v for k,v in result.items() if k!='created'}
        return result

    def heartbeat(self,job_id): return self._rpc('heartbeat',job_id)
    def finish(self,job_id,response): return self._rpc('finish',job_id,response)
    def fail(self,job_id,message): return self._rpc('fail',job_id,{'message':message})
