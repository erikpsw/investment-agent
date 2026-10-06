"""US exchange directory, complete quote snapshots and pre-history filters.

The directory is the universe; missing quotes never silently shrink that count.
Scheduled collection keeps thousands of quote requests outside web functions.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment.data.formula_instruments import name_kind
from investment.data.formula_scoring import number

SNAPSHOT = Path(__file__).resolve().parents[1] / 'api/market_snapshots/us-universe.json'
EXCHANGES = {'N': 'NYSE', 'A': 'AMEX', 'P': 'NYSE_ARCA', 'Z': 'CBOE', 'V': 'IEX'}


class USFilters(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    min_market_cap: float | None = Field(default=1_000_000_000, ge=0)
    max_market_cap: float | None = Field(default=None, gt=0)
    min_price: float | None = Field(default=5, ge=0)
    max_price: float | None = Field(default=None, gt=0)
    min_amount: float | None = Field(default=1_000_000, ge=0)
    exchange: Literal['NASDAQ', 'NYSE', 'AMEX', 'NYSE_ARCA', 'CBOE', 'IEX'] | None = None

    @model_validator(mode='after')
    def ranges(self):
        for lower, upper in [('min_market_cap', 'max_market_cap'), ('min_price', 'max_price')]:
            low, high = getattr(self, lower), getattr(self, upper)
            if low is not None and high is not None and low > high:
                raise ValueError('最低条件不能大于最高条件')
        # Zero explicitly disables a minimum, including its missing-value gate.
        for field in ('min_market_cap', 'min_price', 'min_amount'):
            if getattr(self, field) == 0:
                setattr(self, field, None)
        return self


def filter_rows(rows, filters: USFilters):
    def matches(row):
        if filters.exchange and row.get('exchange') != filters.exchange:
            return False
        for field, lower, upper in [('market_cap', filters.min_market_cap, filters.max_market_cap),
                                    ('price', filters.min_price, filters.max_price),
                                    ('amount', filters.min_amount, None)]:
            if lower is None and upper is None:
                continue
            value = number(row.get(field))
            if value is None or (lower is not None and value < lower) or (upper is not None and value > upper):
                return False
        return True
    return [row for row in rows if matches(row)]


def parse_directory(nasdaq_text: str, other_text: str):
    by_symbol, excluded = {}, Counter()
    listed_count = 0
    for text, is_nasdaq in [(nasdaq_text, True), (other_text, False)]:
        reader = csv.DictReader(io.StringIO(text), delimiter='|')
        required = {'Security Name', 'ETF', 'Test Issue', 'Symbol' if is_nasdaq else 'ACT Symbol'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Nasdaq 目录字段不完整')
        for row in reader:
            ticker = (row.get('Symbol') if is_nasdaq else row.get('ACT Symbol')) or ''
            if ticker.startswith('File Creation Time:') or not ticker:
                continue
            listed_count += 1
            name = row.get('Security Name') or ''
            kind = name_kind(name)
            if row['Test Issue'] != 'N':
                excluded['test'] += 1; continue
            if row['ETF'] != 'N' or row.get('NextShares') == 'Y':
                excluded['etf'] += 1; continue
            if kind is not None:
                excluded[kind] += 1; continue
            # Accept explicitly described common/ordinary shares and equity ADRs.
            if not re.search(r'common (?:stock|shares)|ordinary shares?|depositary (?:shares|receipts)|shares of beneficial interest', name, re.I):
                excluded['unknown'] += 1; continue
            if not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,14}', ticker):
                excluded['unsupported_symbol'] += 1; continue
            exchange = 'NASDAQ' if is_nasdaq else EXCHANGES.get(row.get('Exchange'))
            if exchange is None:
                excluded['unsupported_exchange'] += 1; continue
            by_symbol[ticker] = dict(ticker=ticker, name=name, exchange=exchange, instrument_type='stock',
                                     classification_source='Nasdaq Trader official directory')
    rows = sorted(by_symbol.values(), key=lambda r: r['ticker'])
    return rows, dict(listed_count=listed_count, eligible_count=len(rows),
                      excluded_count=listed_count-len(rows), excluded_by_type=dict(excluded))


def validate_quote_pages(pages):
    if not pages or not isinstance(pages[0].get('total'), int) or pages[0]['total'] <= 0:
        raise ValueError('美股分页总数无效')
    total = pages[0]['total']
    seen, rows = set(), []
    for page in pages:
        if page.get('total') != total or not isinstance(page.get('diff'), list):
            raise ValueError('美股分页总数发生变化，请重新采集')
        for row in page['diff']:
            identity = (row.get('f13'), row.get('f12'))
            if not identity[1] or identity in seen:
                raise ValueError('美股分页缺少代码或存在重复')
            seen.add(identity); rows.append(row)
    if len(rows) != total:
        raise ValueError('美股行情分页不完整，不能替换已有快照')
    return rows


def parse_tencent_quotes(text, identities, *, now=None):
    now = now or datetime.now(timezone.utc)
    rows = []
    for ticker, raw in re.findall(r'v_us([A-Za-z0-9.-]+)="([^"]*)";', text):
        identity = identities.get(ticker)
        values = raw.split('~')
        if not identity or len(values) < 46 or values[35] != 'USD':
            continue
        returned = re.sub(r'\.(?:OQ|N|A|P|Z|V)$', '', values[2])
        if returned != ticker:
            continue
        try:
            stamp = datetime.strptime(values[30], '%Y-%m-%d %H:%M:%S').replace(tzinfo=ZoneInfo('America/New_York'))
        except ValueError:
            continue
        if now-stamp > timedelta(days=7) or stamp > now+timedelta(minutes=1):
            continue
        def value(index):
            try:
                return number(float(values[index])) if values[index] else None
            except ValueError:
                return None
        price, cap = value(3), value(45)
        if price is None or price <= 0:
            continue
        rows.append({**identity, 'market': 'US', 'currency': 'USD', 'price': price,
                     'volume': value(6), 'amount': value(37), 'market_cap': cap*1e8 if cap is not None and cap > 0 else None,
                     'today_change_percent': value(32), 'pe_ratio': value(39), 'pb_ratio': None,
                     'quote_as_of': stamp.isoformat(), 'valuation_basis': 'Tencent provider PE; current snapshot, not historical PIT'})
    return rows


def _timestamp(value, now):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else None
    if stamp is None or stamp.tzinfo is None or stamp > now+timedelta(minutes=1) or now-stamp > timedelta(days=7):
        raise ValueError('美股目录或行情已超过七日有效期')
    return stamp


def read_us_snapshot(path=SNAPSHOT, *, now=None):
    now = now or datetime.now(timezone.utc)
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('version') != 'us-universe-v1' or payload.get('market') != 'US':
        raise ValueError('美股快照版本或市场无效')
    _timestamp(payload.get('generated_at'), now)
    _timestamp(payload.get('directory_generated_at'), now)
    directory = payload.get('directory')
    if not isinstance(directory, list) or not directory:
        raise ValueError('美股证券目录为空')
    identities = {row['ticker']: row for row in directory}
    if len(identities) != len(directory) or any(not re.fullmatch(r'[A-Z][A-Z0-9.-]{0,14}', ticker) or row.get('instrument_type') != 'stock' for ticker, row in identities.items()):
        raise ValueError('美股证券目录代码或类型无效')
    rows, seen = payload.get('rows'), set()
    if not isinstance(rows, list) or not rows:
        raise ValueError('美股行情覆盖为空')
    for row in rows:
        ticker = row.get('ticker')
        identity = identities.get(ticker)
        if ticker in seen or not identity or row.get('market') != 'US' or row.get('currency') != 'USD' or row.get('exchange') != identity.get('exchange'):
            raise ValueError('美股行情身份或币种与目录不一致')
        seen.add(ticker)
        if number(row.get('price')) is None or row['price'] <= 0:
            raise ValueError('美股快照价格无效')
        _timestamp(row.get('quote_as_of'), now)
        for key in ('amount', 'market_cap', 'volume', 'pe_ratio', 'pb_ratio', 'today_change_percent'):
            value = row.get(key)
            if value is not None and number(value) is None:
                raise ValueError('美股快照指标无效')
        if any(row.get(key) is not None and row[key] < 0 for key in ('amount', 'market_cap', 'volume')):
            raise ValueError('美股市值或成交指标为负')
    return {**payload, 'universe_count': len(directory), 'quote_coverage_count': len(rows),
            'quote_missing_count': len(directory)-len(rows), 'cached': True, 'stale': True}
