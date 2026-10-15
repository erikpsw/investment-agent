"""Dated historical factors shared by Actions and request-time US scoring."""
import json
from datetime import date
from pathlib import Path
from investment.data.foreign_formula import completed_date

PATH = Path(__file__).resolve().parents[1] / 'api/market_snapshots/us-history.json'
FIELDS = ('history_as_of', 'change_5d', 'change_20d', 'change_60d', 'risk_bars', 'trend_history')


def read_cache(path=PATH):
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload['items'] if payload.get('version') == 1 and isinstance(payload.get('items'), dict) else {}
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def apply_cached_history(rows, cached=None):
    cached = read_cache() if cached is None else cached
    output = []
    for original in rows:
        row = {k: v for k, v in original.items() if k not in FIELDS}
        factors = cached.get(row['ticker'], {})
        try:
            if not row.get('quote_as_of'):
                raise ValueError('Missing native quote clock')
            cutoff = date.fromisoformat(completed_date(row.get('quote_as_of'), 'US'))
            lag = (cutoff - date.fromisoformat(factors['history_as_of'])).days
            valid = 0 <= lag <= 7
        except (ValueError, TypeError, KeyError):
            valid = False
        if valid:
            row.update({k: factors[k] for k in FIELDS if k in factors})
        else:
            row.update(history_cache_missing=True, history_error='历史缓存缺失或过期，趋势与保护价保持缺失')
        output.append(row)
    return output
