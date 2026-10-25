"""Provider quote clocks, never request time masquerading as market time."""
import math,re
from datetime import datetime
from zoneinfo import ZoneInfo


def parse_quote(text,ticker,now=None):
    now=now or datetime.now(ZoneInfo('Asia/Shanghai'))
    match=re.search(r'v_'+re.escape(ticker)+r'="([^"]+)"',text)
    if not match:raise ValueError('missing_quote_identity')
    fields=match.group(1).split('~')
    if len(fields)<=30 or fields[2]!=ticker[2:]:raise ValueError('wrong_security')
    price=float(fields[3])
    if not math.isfinite(price) or price<=0:raise ValueError('invalid_price')
    stamp=datetime.strptime(fields[30],'%Y%m%d%H%M%S').replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    age=(now-stamp).total_seconds()
    if age<0:raise ValueError('future_quote')
    minute=now.hour*60+now.minute
    during_session=now.weekday()<5 and (570<=minute<=690 or 780<=minute<=900)
    return dict(ticker=ticker,name=fields[1],price=price,price_basis='unadjusted',
                quote_as_of=stamp.isoformat(),fetched_at=now.isoformat(),fresh=age<=120 and during_session,
                quote_age_seconds=age,source='Tencent HTTPS original quote clock',
                note='fresh仅表示交易时段内且原始报价不超过120秒，不保证无延迟或可成交。')
