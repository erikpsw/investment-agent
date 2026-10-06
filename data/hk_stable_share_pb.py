"""Research-only book-period bridge backed by an unchanged, continuous monthly share chain."""
import calendar
import copy
from datetime import date
import math
from investment.data.hk_reviewed_fundamentals import _ordered, _day, _source, _known
from investment.data.formula_scoring import number


def require(condition,message):
    if not condition: raise ValueError(message)


def next_month_end(end):
    year,month=(end.year+1,1) if end.month==12 else (end.year,end.month+1)
    return date(year,month,calendar.monthrange(year,month)[1])


def attach_stable_share_pb(series,book_snapshot,share_snapshot):
    require('hk00388' in series,'HKEX reviewed counter required')
    books=book_snapshot['book_ledger'];shares=share_snapshot['share_ledger']
    _ordered(books);_ordered(shares)
    for row in shares:
        end=_day(row['period_end']);require(end.day==calendar.monthrange(end.year,end.month)[1],'Month-end count required')
        values=[row.get(k) for k in ('issued_excluding_treasury','treasury_shares','total_issued')]
        require(all(type(v) is int for v in values) and values[0]>0 and values[1]>=0 and values[0]+values[1]==values[2],
                'Invalid monthly share columns');_source(row['source_url'],'hkex')
    for row in books:
        require(number(row.get('owner_equity_hkd')) is not None and row['owner_equity_hkd']>0,'Positive owner equity required')
        _source(row['source_url'],'hkex')
    result=copy.deepcopy(series);previous_day=None;previous_scale=None;last_split=None
    for bar in result['hk00388']:
        current=_day(bar['date']);require(previous_day is None or previous_day<current,'Unordered price history');previous_day=current
        scale=number(bar.get('share_scale'))
        if scale is not None and scale>0:
            if previous_scale is not None and abs(scale/previous_scale-1)>.2: last_split=bar['date']
            previous_scale=scale
        if number(bar.get('pb_ratio')) is not None: continue
        cap=number(bar.get('market_cap'));price=number(bar.get('raw_close'))
        if cap is None or cap<=0 or price is None or price<=0 or number(bar.get('pe_ratio')) is None: continue
        require(isinstance(bar.get('metrics_as_of'),str) and bar['metrics_as_of']<=bar['date'],'Future baseline valuation')
        book=_known(books,bar['date']);latest=_known(shares,bar['date'])
        if book is None or latest is None or (current-_day(latest['period_end'])).days>45 or (current-_day(book['period_end'])).days>400: continue
        known=[s for s in shares if s['available']<=bar['date']]
        anchors=[s for s in known if abs((_day(s['period_end'])-_day(book['period_end'])).days)<=8]
        if len(anchors)!=1: continue
        anchor=anchors[0]
        if last_split and anchor['period_end']<last_split: continue
        chain=[s for s in known if anchor['period_end']<=s['period_end']<=latest['period_end']]
        keys=('issued_excluding_treasury','treasury_shares','total_issued')
        if not chain or any(any(s[k]!=anchor[k] for k in keys) for s in chain): continue
        if any(_day(b['period_end'])!=next_month_end(_day(a['period_end'])) for a,b in zip(chain,chain[1:])): continue
        expected=price*latest['issued_excluding_treasury']
        require(number(expected) is not None and math.isclose(cap,expected,rel_tol=1e-12),'Current market cap/share arithmetic differs')
        pb=cap/book['owner_equity_hkd']
        if number(pb) is None or pb<=0: continue
        sources=list(dict.fromkeys([*bar.get('fundamentals_accessions',[]),book['source_url'],*[s['source_url'] for s in chain]]))
        bar.update(pb_ratio=pb,book_period_end=book['period_end'],book_available=book['available'],
            metrics_as_of=max(bar['metrics_as_of'],book['available'],latest['available']),
            fundamentals_accessions=sources,pb_shares_period_end=anchor['period_end'],
            pb_share_continuity_verified_through=latest['period_end'],pb_bridge_months=len(chain),
            pb_owner_equity_hkd=book['owner_equity_hkd'],pb_anchor_share_count=anchor['issued_excluding_treasury'],
            fundamentals_reference_only=True,pb_reference_policy='unchanged-monthly-share-book-anchor-v1')
    return result
