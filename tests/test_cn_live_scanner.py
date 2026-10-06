from datetime import datetime, timezone
import pytest
from investment.data import cn_live_scanner as live


def row(symbol='sh600519', **changes):
    return dict(symbol=symbol, name='测试股份', trade='10.25', amount=900000000,
                mktcap=2000000, nmc=1000000, per=12, pb=1.2,
                changepercent=2, turnoverratio=1.5, **changes)


def test_provider_units_and_missing_factors():
    result=live.normalize(row())
    assert result['market_cap']==20000000000
    assert result['float_market_cap']==10000000000
    assert result['amount']==900000000
    assert result['price']==10.25 and result['market']=='CN'
    assert 'volume_ratio' not in result and 'change_60d' not in result


@pytest.mark.parametrize('changes',[{'symbol':'sh688001'}, {'symbol':'bj920001'},
    {'name':'*ST测试'}, {'name':'测试退'}, {'trade':'NaN'}, {'trade':True},
    {'amount':0}, {'mktcap':'Infinity'}])
def test_ineligible_or_invalid_quotes_are_excluded(changes):
    original=row();original.update(changes)
    assert live.normalize(original) is None


def quote(symbol='sh600519',price='10.250',date='2026-09-30',clock='15:00:00'):
    parts=['测试']+['0']*32
    parts[3]=price;parts[30]=date;parts[31]=clock
    return 'var hq_str_'+symbol+'="'+','.join(parts)+'";'


def test_quote_date_is_native_and_price_is_paired():
    data=live.quote_times(quote(),[live.normalize(row())],now=datetime(2026,10,5,tzinfo=timezone.utc))
    assert data=={'sh600519':'2026-09-30T15:00:00+08:00'}
    assert live.quote_times(quote(price='10.260'),[live.normalize(row())],now=datetime(2026,10,5,tzinfo=timezone.utc))=={}


@pytest.mark.parametrize('date,clock',[('2026-10-06','15:00:00'),('2026-02-30','15:00:00'),('2026-09-30','25:00:00'),('2026-08-01','15:00:00')])
def test_future_invalid_or_over_seven_day_dates_rejected(date,clock):
    assert live.quote_times(quote(date=date,clock=clock),[live.normalize(row())],now=datetime(2026,10,5,tzinfo=timezone.utc))=={}


def test_primary_scanner_result_preserved(monkeypatch):
    expected={'rows':[],'source':'primary'}
    monkeypatch.setattr(live.base,'scan_cn_market',lambda:expected)
    assert live.scan_cn_market() is expected


def test_primary_generation_clock_is_not_used_as_quote_clock(monkeypatch):
    payload={'rows':[{'ticker':'sh600519','price':10}], 'source':'provider scan',
             'generated_at':'2026-10-05T00:00:00Z'}
    monkeypatch.setattr(live.base,'scan_cn_market',lambda:payload)
    assert live.scan_cn_market()['rows'][0]['quote_as_of'] is None


def test_failed_primary_requires_complete_dated_universe(monkeypatch):
    monkeypatch.setattr(live.base,'scan_cn_market',lambda:(_ for _ in ()).throw(RuntimeError('offline')))
    monkeypatch.setattr(live,'scan_sina_market',lambda:{'rows':[row()]})
    with pytest.raises(RuntimeError): live.scan_cn_market()


def test_native_saved_snapshot_expires_without_relabeling(tmp_path):
    import json
    codes=[f'sh{prefix}{i:03d}' for prefix in ('600','601','603') for i in range(1000)][:2500]
    payload={'rows':[{'ticker':code,'market':'CN','name':'示例股份','price':10,
                     'amount':10000,'market_cap':20000,'quote_as_of':'2026-09-30T15:00:00+08:00'} for code in codes],
             'generated_at':'2026-09-30T15:00:00+08:00','source':'actual Sina capture'}
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(payload),encoding='utf-8')
    result=live.read_saved_snapshot(path,now=datetime(2026,10,5,tzinfo=timezone.utc))
    assert result['generated_at']==payload['generated_at'] and result['cached']
    assert result['rows']==payload['rows']
    with pytest.raises(ValueError):live.read_saved_snapshot(path,now=datetime(2026,10,8,tzinfo=timezone.utc))


def test_missing_saved_snapshot_cannot_fabricate_success(tmp_path):
    with pytest.raises(OSError):live.read_saved_snapshot(tmp_path/'absent.json')
