import json
from datetime import datetime, timezone, date
import pytest
from scripts import refresh_cn_snapshot as worker


def payload(stamp):
    return {'rows': [{'ticker': f'sh600{i:03d}' if i < 1000 else f'sh601{i-1000:03d}' if i < 2000 else f'sh603{i-2000:03d}',
                     'market': 'CN', 'name': '示例股份', 'price': 10, 'amount': 10000,
                     'market_cap': 20000, 'quote_as_of': stamp} for i in range(2500)],
            'generated_at': stamp, 'cached': False}


def test_success_atomically_saves_original_quote_clock(tmp_path):
    path = tmp_path / 'snapshot.json'
    data = payload('2026-10-08T15:00:00+08:00')
    assert worker.refresh(path, fetch=lambda: data, now=datetime(2026,10,8,8,tzinfo=timezone.utc)) == data
    assert json.loads(path.read_text(encoding='utf-8')) == data


@pytest.mark.parametrize('stamp', ['2026-09-30T15:00:00+08:00', '2026-10-09T15:00:00+08:00'])
def test_stale_or_future_provider_data_never_overwrites_cache(tmp_path, stamp):
    path = tmp_path / 'snapshot.json'
    path.write_text('original', encoding='utf-8')
    with pytest.raises(ValueError):
        worker.refresh(path, fetch=lambda: payload(stamp), now=datetime(2026,10,8,8,tzinfo=timezone.utc))
    assert path.read_text() == 'original'


def test_provider_failure_preserves_cache(tmp_path):
    path = tmp_path / 'snapshot.json'
    path.write_text('original')
    def fail():
        raise RuntimeError('offline')
    with pytest.raises(RuntimeError):
        worker.refresh(path, fetch=fail, now=datetime(2026,10,8,8,tzinfo=timezone.utc))
    assert path.read_text() == 'original'


def test_holiday_skips_provider_and_makeup_weekend_is_closed(tmp_path):
    assert worker.refresh(tmp_path/'snapshot.json', fetch=lambda: pytest.fail('holiday request'),
                          now=datetime(2026,10,7,8,tzinfo=timezone.utc)) is None
    assert not worker.is_session(date(2026,10,10))
    assert not worker.is_session(date(2026,1,1))
    assert worker.is_session(date(2026,10,8))
