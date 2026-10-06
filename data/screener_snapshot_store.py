"""Service-only last successful snapshots; caller dates are never renewed."""
import copy
import os
from datetime import datetime, timezone
import requests
from investment.data.screener_cloud_jobs import CloudJobStore, CloudStoreUnavailable


def _now():
    return datetime.now(timezone.utc)


def validate_snapshot(market, payload):
    payload = copy.deepcopy(payload)
    if market == 'CN':
        from investment.data.cn_live_scanner import validate_saved_snapshot
        result = validate_saved_snapshot(payload, now=_now())
    elif market in ('HK', 'US'):
        from investment.data.foreign_live_scanner import validate_foreign_snapshot
        result = validate_foreign_snapshot(market, payload, now=_now())
    else:
        raise ValueError('Invalid market')
    result['market'] = market
    return result


class CloudSnapshotStore:
    def __init__(self, url, key):
        transport = CloudJobStore(url, key)
        self.url = transport.url.rsplit('/', 1)[0] + '/screener_snapshot_rpc'
        self.headers = transport.headers

    def _rpc(self, operation, market, payload=None):
        try:
            response = requests.post(self.url, headers=self.headers,
                json={'operation': operation, 'market_name': market, 'payload': payload}, timeout=5, allow_redirects=False)
            return response.json() if response.status_code == 200 else None
        except (requests.RequestException, ValueError):
            return None

    def load(self, market):
        try:
            result = validate_snapshot(market, self._rpc('get', market))
            result['source'] += '；云端缓存'
            return result
        except (ValueError, TypeError, KeyError, OverflowError):
            return None

    def save(self, market, payload):
        try:
            validate_snapshot(market, payload)
        except (ValueError, TypeError, KeyError, OverflowError):
            return False
        # Preserve actual provider payload, including its original source/clock.
        value = {**copy.deepcopy(payload), 'market': market}
        return self._rpc('put', market, value) is True


def snapshot_store():
    if not os.getenv('VERCEL') or os.getenv('SCREENER_JOB_BACKEND') != 'supabase':
        return None
    try:
        return CloudSnapshotStore(os.getenv('SUPABASE_URL', ''), os.getenv('SUPABASE_SERVICE_KEY', ''))
    except (CloudStoreUnavailable, ValueError):
        return None


def remember_snapshot(market, payload):
    if payload.get('cached') or payload.get('stale'):
        return False
    store = snapshot_store()
    return store.save(market, payload) if store else False


def restore_snapshot(market):
    store = snapshot_store()
    return store.load(market) if store else None
