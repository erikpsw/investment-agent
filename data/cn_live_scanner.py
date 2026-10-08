"""Full A-share fallback with native quote dates; frozen research scanner stays intact."""
from __future__ import annotations

import math
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Lock
from pathlib import Path

import requests
from investment.data import market_scanner as base
from investment.data.screener_snapshot_store import remember_snapshot, restore_snapshot

API = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.'
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'}
MINIMUM = 2500
SNAPSHOT = Path(__file__).resolve().parents[1] / 'api/market_snapshots/cn-sina.json'
_cache = None
_lock = Lock()


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def normalize(raw):
    if not isinstance(raw, dict):
        return None
    ticker = raw.get('symbol')
    name = str(raw.get('name') or '').strip()
    if not isinstance(ticker, str) or not re.fullmatch(r'(?:sh(?:600|601|603|605)|sz(?:000|001|002|003))\d{3}', ticker):
        return None
    if not name or 'ST' in name.upper() or '退' in name:
        return None
    price, amount, cap = (number(raw.get(key)) for key in ('trade', 'amount', 'mktcap'))
    if any(value is None or value <= 0 for value in (price, amount, cap)):
        return None
    result = {'ticker': ticker, 'name': name, 'market': 'CN', 'price': price,
              'amount': amount, 'market_cap': cap * 10000}
    for original, target, multiplier in [('nmc', 'float_market_cap', 10000), ('per', 'pe_ratio', 1),
            ('pb', 'pb_ratio', 1), ('changepercent', 'today_change_percent', 1),
            ('turnoverratio', 'turnover_rate', 1)]:
        value = number(raw.get(original))
        if value is not None and math.isfinite(value * multiplier):
            result[target] = value * multiplier
    return result


def quote_is_current(stamp, now):
    """Use the shared exchange calendar without renewing the provider clock."""
    from investment.data.formula_risk import history_timing
    if stamp.tzinfo is None or stamp > now + timedelta(minutes=1):
        return False
    timing = history_timing({'market': 'CN', 'quote_as_of': now.isoformat()},
                            stamp.astimezone(timezone(timedelta(hours=8))).date().isoformat())
    if 'history_lag_trading_days' in timing:
        return timing['status'] == 'ok'
    return now - stamp <= timedelta(days=7)


def quote_times(text, rows, *, now=None):
    now = now or datetime.now(timezone.utc)
    expected = {row['ticker']: row['price'] for row in rows}
    result = {}
    for ticker, content in re.findall(r'var\s+hq_str_((?:sh|sz)\d{6})="([^"\r\n]*)";', text):
        fields = content.split(',')
        if ticker not in expected or ticker in result or len(fields) < 32:
            continue
        price = number(fields[3])
        if price is None or abs(price - expected[ticker]) > 0.0001:
            continue
        try:
            stamp = datetime.fromisoformat(fields[30] + 'T' + fields[31] + '+08:00')
        except ValueError:
            continue
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', fields[30]) or not re.fullmatch(r'\d{2}:\d{2}:\d{2}', fields[31]):
            continue
        if not quote_is_current(stamp, now):
            continue
        result[ticker] = stamp.isoformat()
    return result


def _get(url, params=None):
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=8)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            status = getattr(exc.response, 'status_code', None)
            if attempt == 2 or (status is not None and status < 500 and status not in (408, 429)):
                raise
            time.sleep(0.5 * 2 ** attempt)


def scan_sina_market():
    global _cache
    with _lock:
        if _cache and time.monotonic() < _cache[0]:
            return {**_cache[1], 'rows': [dict(row) for row in _cache[1]['rows']], 'cached': True}
    count = int(_get(API + 'getHQNodeStockCount', {'node': 'hs_a'}).json())
    if not 2500 <= count <= 10000:
        raise RuntimeError('全市场股票数量不完整')

    def page(index):
        payload = _get(API + 'getHQNodeData', {'page': index, 'num': 80, 'sort': 'symbol',
            'asc': 1, 'node': 'hs_a', 'symbol': '', '_s_r_a': 'page'}).json()
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise RuntimeError('全市场行情分页无效')
        return payload

    with ThreadPoolExecutor(max_workers=8) as executor:
        raw = [row for batch in executor.map(page, range(1, math.ceil(count / 80) + 1)) for row in batch]
    symbols = [row.get('symbol') for row in raw]
    if len(raw) != count or not all(isinstance(value, str) for value in symbols) or len(set(symbols)) != count:
        raise RuntimeError('全市场行情分页缺失或重复')
    rows = [value for value in map(normalize, raw) if value is not None]
    if len(rows) < MINIMUM:
        raise RuntimeError('主板行情数量不完整')

    def dates(batch):
        response = _get('https://hq.sinajs.cn/list=' + ','.join(row['ticker'] for row in batch))
        return quote_times(response.text, batch)

    with ThreadPoolExecutor(max_workers=8) as executor:
        timestamps = {}
        for batch in executor.map(dates, [rows[i:i+150] for i in range(0, len(rows), 150)]):
            timestamps.update(batch)
    dated = [{**row, 'quote_as_of': timestamps[row['ticker']]} for row in rows if row['ticker'] in timestamps]
    if len(dated) < MINIMUM:
        raise RuntimeError('具有原始日期且价格一致的全市场行情不完整')
    snapshot = {'rows': dated, 'generated_at': max(row['quote_as_of'] for row in dated),
        'retrieved_at': datetime.now(timezone.utc).isoformat(), 'cached': False,
        'source': '新浪财经沪深主板非ST全市场；报价日期来自原始行情，非抓取时间；仅保留价格一致且有效期内的报价（已配置日历按5个交易日，其他年份按7个自然日）',
        'provider_count': count, 'quote_verified_count': len(dated)}
    with _lock:
        _cache = (time.monotonic() + 600, snapshot)
    return snapshot


def scan_cn_market():
    try:
        snapshot = base.scan_cn_market()
        snapshot['rows'] = [{**row, 'quote_as_of': row.get('quote_as_of')} for row in snapshot.get('rows', [])]
        snapshot['source'] = str(snapshot.get('source') or '东方财富全市场行情') + '；数据时间为快照生成时间，缺少原始日期的逐只报价标为未核验'
        return snapshot
    except Exception:
        try:
            result = scan_sina_market()
        except Exception:
            result = restore_snapshot('CN') or read_saved_snapshot()
        if len(result.get('rows', [])) < MINIMUM or not result.get('generated_at'):
            raise RuntimeError('全市场行情数量或日期不完整')
        remember_snapshot('CN', result)
        return result


def read_saved_snapshot(path=SNAPSHOT, *, now=None):
    payload = json.loads(path.read_text(encoding='utf-8'))
    return validate_saved_snapshot(payload, now=now)


def validate_saved_snapshot(payload, *, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, dict):
        raise ValueError('保存的全市场行情格式无效')
    rows = payload.get('rows')
    if not isinstance(rows, list) or not MINIMUM <= len(rows) <= 10000:
        raise ValueError('保存的全市场行情数量不完整')
    tickers = set()
    timestamps = []
    for row in rows:
        if not isinstance(row, dict) or row.get('market') != 'CN':
            raise ValueError('保存的全市场行情市场无效')
        ticker = row.get('ticker')
        if not isinstance(ticker, str) or not re.fullmatch(r'(?:sh(?:600|601|603|605)|sz(?:000|001|002|003))\d{3}', ticker) or ticker in tickers:
            raise ValueError('保存的全市场行情代码无效或重复')
        tickers.add(ticker)
        name = row.get('name')
        if not isinstance(name, str) or not name or 'ST' in name.upper() or '退' in name:
            raise ValueError('保存的全市场行情名称无效')
        for key in ('price', 'amount', 'market_cap'):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('保存的全市场行情价格或金额无效')
        for key in ('float_market_cap', 'pe_ratio', 'pb_ratio', 'today_change_percent', 'turnover_rate'):
            value = row.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('保存的全市场行情指标无效')
        stamp = row.get('quote_as_of')
        if not isinstance(stamp, str):
            raise ValueError('保存的全市场行情缺少原始报价时间')
        parsed = datetime.fromisoformat(stamp)
        if parsed.isoformat() != stamp or not quote_is_current(parsed, now):
            raise ValueError('保存的全市场行情原始报价过期或无效')
        timestamps.append(stamp)
    if payload.get('generated_at') != max(timestamps):
        raise ValueError('保存的全市场行情时间与原始报价不一致')
    return {**payload, 'cached': True, 'stale': True,
            'source': '新浪财经保存的沪深主板非ST全市场快照；非实时；保留原始报价日期（已配置日历按5个交易日，其他年份按7个自然日过期）'}
