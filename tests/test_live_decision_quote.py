from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from data.live_decision_quote import parse_quote


def text(stamp='20261023100000',code='600519'):
    fields=['']*40;fields[1]='贵州茅台';fields[2]=code;fields[3]='1500';fields[4]='1490';fields[30]=stamp
    return 'v_sh600519="'+'~'.join(fields)+'";'


def test_only_original_fresh_provider_clock_is_live():
    now=datetime(2026,10,23,10,0,30,tzinfo=ZoneInfo('Asia/Shanghai'))
    q=parse_quote(text(),'sh600519',now)
    assert q['fresh'] and q['price_basis']=='unadjusted'
    closed=parse_quote(text(),'sh600519',datetime(2026,10,25,10,tzinfo=now.tzinfo))
    assert not closed['fresh']


def test_future_and_wrong_security_quotes_fail_closed():
    now=datetime(2026,10,23,10,tzinfo=ZoneInfo('Asia/Shanghai'))
    with pytest.raises(ValueError):parse_quote(text(code='600000'),'sh600519',now)
    with pytest.raises(ValueError):parse_quote(text(stamp='20261023110000'),'sh600519',now)
