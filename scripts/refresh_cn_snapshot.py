"""Refresh the dated CN fallback; failed downloads never overwrite saved quotes."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from investment.data.cn_live_scanner import SNAPSHOT, scan_sina_market, validate_saved_snapshot, read_saved_snapshot, scan_tencent_market
from investment.data.formula_risk import history_timing


def is_session(day):
    # The shared lag helper falls back at year boundaries; Jan 1 is a
    # published closure in the configured 2026 exchange calendar.
    if day.isoformat() == '2026-01-01':
        return False
    timing = history_timing({'market': 'CN', 'quote_as_of': day.isoformat()},
                            (day - timedelta(days=1)).isoformat())
    return timing.get('history_lag_trading_days', int(day.weekday() < 5)) == 1


def refresh(path=SNAPSHOT, *, fetch=None, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(timezone(timedelta(hours=8))).date()
    if not is_session(today):
        return None
    local_now = now.astimezone(timezone(timedelta(hours=8)))
    expected = today if local_now.hour >= 15 else today - timedelta(days=1)
    while not is_session(expected):
        expected -= timedelta(days=1)
    errors = []
    for provider in ([fetch] if fetch else [scan_sina_market, scan_tencent_market]):
        try:
            payload = provider()
            validate_saved_snapshot(payload, now=now)
            quote_day = datetime.fromisoformat(payload['generated_at']).astimezone(
                timezone(timedelta(hours=8))).date()
            if quote_day < expected:
                raise ValueError(f'供应商报价 {quote_day} 早于最近完成交易日 {expected}')
            break
        except Exception as exc:
            if fetch:
                raise
            errors.append(f'{provider.__name__}: {exc}')
    else:
        raise RuntimeError('；'.join(errors))
    temporary = path.with_suffix('.tmp')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def main():
    try:
        payload = refresh()
        message = (f"A股备用快照更新成功：{len(payload['rows'])}只，原始报价时间 {payload['generated_at']}"
                   if payload else 'A股休市，跳过更新并保留原始报价日期')
        code = 0
    except Exception as exc:
        try:
            cached = read_saved_snapshot()
            message = f'::warning::A股备用快照未更新，继续使用有效缓存 {cached["generated_at"]}；非实时。原因：{exc}'
            code = 0
        except Exception as cache_exc:
            message = f'A股备用快照更新失败，且无有效缓存：{exc}；缓存校验：{cache_exc}'
            code = 1
    print(message)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as output:
            output.write(message + '\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
