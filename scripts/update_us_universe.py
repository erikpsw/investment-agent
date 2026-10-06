"""Collect the full US directory and all quote pages, then atomically publish."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import requests
from investment.data.us_universe import parse_directory, validate_quote_pages, read_us_snapshot, parse_tencent_quotes, SNAPSHOT
from investment.data.formula_scoring import number
from investment.data.quote_timing import epoch_quote_time_fields

HEADERS = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
QUOTE_URLS = ['https://push2.eastmoney.com/api/qt/clist/get', 'https://push2delay.eastmoney.com/api/qt/clist/get', 'https://82.push2.eastmoney.com/api/qt/clist/get']


def get(urls, *, params=None, as_json=False):
    last = None
    for attempt in range(5):
        try:
            response = requests.get(urls[attempt % len(urls)], params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()
            if 'qt.gtimg.cn' in response.url:
                response.encoding = 'gb18030'
            return response.json() if as_json else response.text
        except (requests.RequestException, ValueError) as exc:
            last = exc
            time.sleep(min(2, .4*(attempt+1)))
    raise RuntimeError(f'Data source unavailable: {urls[0]}') from last


def collect():
    texts = []
    for filename in ('nasdaqlisted.txt', 'otherlisted.txt'):
        text = get([f'https://{host}/dynamic/SymDir/{filename}' for host in ('www.nasdaqtrader.com', 'nasdaqtrader.com')])
        if 'File Creation Time:' not in text:
            raise ValueError('Official directory footer missing')
        # The published file clock uses US Eastern time.
        from zoneinfo import ZoneInfo
        footer = text.split('File Creation Time: ', 1)[1].split('|', 1)[0].strip()
        directory_time = datetime.strptime(footer, '%m%d%Y%H:%M').replace(tzinfo=ZoneInfo('America/New_York'))
        now = datetime.now(timezone.utc)
        if directory_time > now+timedelta(hours=24) or now-directory_time > timedelta(days=7):
            raise ValueError('Official directory is stale or future dated')
        texts.append(text)
    directory, stats = parse_directory(*texts)
    if len(directory) < 3000:
        raise ValueError('Incomplete official US directory')
    identities = {row['ticker']: row for row in directory}
    batches = [directory[index:index+50] for index in range(0, len(directory), 50)]
    def batch(entries):
        text = get(['https://qt.gtimg.cn/q='+','.join('us'+row['ticker'] for row in entries)])
        return parse_tencent_quotes(text, {row['ticker']:row for row in entries})
    # Request every directory symbol. Empty responses are counted as missing quotes.
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(batch, batches))
    tencent_rows = [row for result in results for row in result]
    now = datetime.now(timezone.utc)
    if len(tencent_rows) >= len(directory)*.7:
        return dict(version='us-universe-v1', market='US', generated_at=now.isoformat(), directory_generated_at=now.isoformat(),
                    directory_source_urls=['https://www.nasdaqtrader.com/dynamic/SymDir/'+f for f in ('nasdaqlisted.txt','otherlisted.txt')],
                    directory_file_sha256=[hashlib.sha256(text.encode()).hexdigest() for text in texts],
                    directory=directory, directory_stats=stats, rows=sorted(tencent_rows, key=lambda r:r['ticker']),
                    quote_requested_count=len(directory), quote_batch_count=len(batches),
                    source='Nasdaq Trader official directory + Tencent US delayed batch quotes')
    print('Tencent coverage below 70%; trying complete Eastmoney quote pages', flush=True)
    params = dict(pz=100, po=1, np=1, fltt=2, invt=2, fid='f12', fs='m:105,m:106,m:107', fields='f12,f14,f2,f3,f5,f6,f20,f13,f124,f9,f23')
    def page(index):
        result = get(QUOTE_URLS, params={**params, 'pn': index}, as_json=True).get('data')
        if not isinstance(result, dict):
            raise ValueError('Quote page missing')
        return result
    first = page(1)
    with ThreadPoolExecutor(max_workers=6) as executor:
        pages = [first, *executor.map(page, range(2, math.ceil(first['total']/100)+1))]
    quotes = validate_quote_pages(pages)
    identities = {row['ticker']: row for row in directory}
    output = {}
    now = datetime.now(timezone.utc)
    for quote in quotes:
        ticker = str(quote.get('f12') or '').upper().replace('/', '.')
        identity = identities.get(ticker)
        if not identity:
            continue
        stamp = epoch_quote_time_fields(quote.get('f124'))['timestamp']
        price = number(quote.get('f2'))
        if price is None or price <= 0 or stamp is None:
            continue
        quote_date = datetime.fromisoformat(stamp)
        if quote_date > now+timedelta(minutes=1) or now-quote_date > timedelta(days=7):
            continue
        if ticker in output:
            raise ValueError(f'Duplicate normalized stock symbol: {ticker}')
        output[ticker] = {**identity, 'market': 'US', 'currency': 'USD', 'price': price,
                          'quote_as_of': stamp, 'quote_time': quote.get('f124'),
                          'today_change_percent': number(quote.get('f3')), 'volume': number(quote.get('f5')),
                          'amount': number(quote.get('f6')), 'market_cap': number(quote.get('f20')),
                          'pe_ratio': number(quote.get('f9')), 'pb_ratio': number(quote.get('f23'))}
    if len(output) < len(directory)*.7:
        raise ValueError(f'Quote coverage too low: {len(output)}/{len(directory)}')
    return dict(version='us-universe-v1', market='US', generated_at=now.isoformat(), directory_generated_at=now.isoformat(),
                directory_source_urls=['https://www.nasdaqtrader.com/dynamic/SymDir/'+f for f in ('nasdaqlisted.txt','otherlisted.txt')],
                directory_file_sha256=[hashlib.sha256(text.encode()).hexdigest() for text in texts],
                directory=directory, directory_stats=stats, rows=sorted(output.values(), key=lambda r:r['ticker']),
                quote_provider_total=first['total'], quote_page_count=len(pages),
                source='Nasdaq Trader official directory + Eastmoney US delayed market quotes')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=SNAPSHOT)
    args = parser.parse_args()
    payload = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp.json')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        validated = read_us_snapshot(temporary)
        os.replace(temporary, args.output)
        print(json.dumps({key:validated[key] for key in ('universe_count','quote_coverage_count','quote_missing_count','generated_at')}))
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
