"""On-demand, closed-bar diagnostics for the selected weekly momentum policy."""
import math
import struct
from datetime import date, timedelta


def parse_bars(payload, ticker, basis):
    if payload.get('code') not in (0, '0'):
        raise ValueError('provider_error')
    node=payload.get('data',{}).get(ticker,{})
    rows=node.get('hfqday' if basis=='hfq' else 'day')
    if not rows:raise ValueError('missing_verified_price_basis')
    bars=[]
    for row in rows:
        day=date.fromisoformat(row[0]).isoformat()
        o,c,h,l,v=map(float,row[1:6])
        if not all(math.isfinite(x) for x in (o,c,h,l,v)) or min(o,c,h,l)<=0 or v<0 or h<max(o,c,l) or l>min(o,c,h):raise ValueError('invalid_ohlcv')
        if bars and day<=bars[-1][0]:raise ValueError('unordered_dates')
        bars.append([day,o,h,l,c,v])
    return bars


def analyze(stock, benchmark, now):
    today=now.date().isoformat()
    def closed(rows):return [b for b in rows if b[0]<today or (b[0]==today and now.hour>=15)]
    stock,benchmark=closed(stock),closed(benchmark)
    if len(stock)<200 or len(benchmark)<120:raise ValueError('insufficient_history')
    market_day=benchmark[-1][0]
    cutoff=date.fromisoformat(market_day)
    cutoff+=timedelta(days=4-cutoff.weekday())
    if cutoff.isoformat()>market_day:cutoff-=timedelta(days=7)
    weeks={}
    for bar in stock:
        day=date.fromisoformat(bar[0]);friday=day+timedelta(days=4-day.weekday())
        if friday<=cutoff:weeks[friday.isoformat()]=bar[4]
    dates=sorted(weeks)
    momentum=None
    if len(dates)>=40 and dates[-1]==cutoff.isoformat():
        value=weeks[dates[-1]]/weeks[dates[-13]]-1
        momentum=struct.unpack('f',struct.pack('f',value))[0]*100
    ma=sum(b[4] for b in benchmark[-120:])/120
    fresh=0<=(now.date()-date.fromisoformat(market_day)).days<=3 and stock[-1][0]==market_day
    return dict(analyzed_at=now.isoformat(),bars=stock[-240:],price_basis='hfq',stock_as_of=stock[-1][0],
                signal_as_of=cutoff.isoformat(),momentum_pct=momentum,data_fresh=fresh,
                market=dict(as_of=market_day,close=benchmark[-1][4],ma=ma,allow_open=benchmark[-1][4]>ma),
                execution_ready=False,policy='momentum-ma120-selected-r2',
                note='重新抓取后按已收盘日线计算；12周动量只使用已结束周线。排名来自整池快照，未在此重排。')
