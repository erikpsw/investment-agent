"""Bounded saved HK fallback; preserves snapshot age and unknown quote dates."""
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from investment.data import foreign_formula as base
from investment.data.formula_instruments import stock_candidates
from investment.data.quote_timing import epoch_quote_time_fields
from investment.data.screener_snapshot_store import remember_snapshot, restore_snapshot

SNAPSHOT = Path(__file__).resolve().parents[1] / 'api/market_snapshots/hot-hk.json'


def read_hk_snapshot(path=SNAPSHOT, *, now=None):
    payload = json.loads(path.read_text(encoding='utf-8'))
    return validate_foreign_snapshot('HK', payload, now=now)


def validate_foreign_snapshot(market, payload, *, now=None):
    now = now or datetime.now(timezone.utc)
    if market not in ('HK', 'US') or not isinstance(payload, dict):
        raise ValueError('外盘缓存市场或格式无效')
    stamp = payload.get('generated_at')
    if payload.get('market') != market or not isinstance(stamp, str):
        raise ValueError('港股缓存市场或日期无效')
    parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed > now + timedelta(minutes=1) or now-parsed > timedelta(days=7):
        raise ValueError('港股缓存过期或时间无效')
    rows = payload.get('rows')
    if not isinstance(rows, list) or len(rows) < 10:
        raise ValueError('港股缓存数量不足')
    tickers = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('market') != market or row.get('currency') != ('HKD' if market == 'HK' else 'USD'):
            raise ValueError('港股缓存市场或币种不一致')
        ticker = row.get('ticker')
        pattern = r'hk\d{5}' if market == 'HK' else r'[A-Z][A-Z0-9.-]{0,14}'
        if not isinstance(ticker, str) or not re.fullmatch(pattern, ticker) or ticker in tickers:
            raise ValueError('港股缓存代码无效或重复')
        tickers.add(ticker)
        for key in ('price', 'amount'):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('港股缓存价格或成交额无效')
        for key in ('market_cap', 'float_market_cap', 'pe_ratio', 'pb_ratio', 'volume_ratio', 'turnover_rate', 'today_change_percent'):
            value = row.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('港股缓存指标无效')
        if market == 'US':
            quote = epoch_quote_time_fields(row.get('quote_time'))['timestamp']
            if not quote or now-datetime.fromisoformat(quote) > timedelta(days=7) or datetime.fromisoformat(quote) > now+timedelta(minutes=1):
                raise ValueError('美股缓存原始报价日期缺失或过期')
    filtered = stock_candidates(rows)
    if len(filtered['rows']) < 10:
        raise ValueError('已核验港股股票候选不足')
    return {**payload, 'rows': [{**row, 'quote_as_of': None if market == 'HK' else epoch_quote_time_fields(row.get('quote_time'))['timestamp']} for row in filtered['rows']],
        'cached': True, 'stale': True,
        'source': str(payload.get('source') or '外盘行情') + '；保存的成交活跃候选快照，非全市场；数据时间为原快照生成时间；' + ('报价日期未核实；' if market == 'HK' else '保留逐只原始报价日期；') + '七日过期',
        'instrument_filter': {key: value for key, value in filtered.items() if key != 'rows'}}


def scan_foreign_market(market):
    try:
        snapshot = base.scan_foreign_market(market)
        rows = []
        for row in snapshot.get('rows', []):
            stamp = row.get('quote_as_of')
            if market == 'US':
                stamp = epoch_quote_time_fields(row.get('quote_time'))['timestamp']
                if stamp and datetime.fromisoformat(stamp) > datetime.now(timezone.utc) + timedelta(minutes=1):
                    stamp = None
            rows.append({**row, 'quote_as_of': stamp})
        snapshot['rows'] = rows
        remember_snapshot(market, snapshot)
        return snapshot
    except Exception:
        saved = restore_snapshot(market)
        if saved:
            return saved
        if market != 'HK':
            raise
        return read_hk_snapshot()
