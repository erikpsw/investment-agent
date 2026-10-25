"""Explicitly labeled archived simulation markers on their original hfq basis."""
def chart_payload(ticker,name,bars,trades):
    dates=[b['date'] for b in bars]
    if dates!=sorted(set(dates)):raise ValueError('unordered_or_duplicate_dates')
    available=set(dates)
    selected=[t for t in trades if t['code']==ticker]
    for t in selected:
        if t['entry_date'] not in available or t['exit_date'] not in available:
            raise ValueError('trade_date_outside_archive')
        if t['exit_date']<t['entry_date']:raise ValueError('exit_before_entry')
    return dict(ticker=ticker,name=name,price_basis='hfq',
                series_kind='archived_research_not_actual_fills',
                bars=[[b[k] for k in ['date','open','high','low','close','volume']] for b in bars],
                trades=selected,trade_scope='reference793_only',
                source_note='Historical simulated fills from the original 793-stock run, not all-market returns or your account fills.')
