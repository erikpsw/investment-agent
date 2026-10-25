"""Explicit equity classification and full-market collection completeness."""
import re


def classify_equity(row,scope='mainboard'):
    ticker=row.get('ticker','');name=row.get('name','').upper()
    if not re.fullmatch(r'(?:sh(?:60|68)\d{4}|sz(?:00|30)\d{4}|bj\d{6})',ticker):
        return 'not_equity'
    if scope not in ('mainboard','all_cn'):raise ValueError('unknown_scope')
    if scope=='mainboard' and not re.fullmatch(r'(?:sh60\d{4}|sz00\d{4})',ticker):
        return 'excluded_board'
    if 'ST' in name or '退' in name:return 'st_or_delisting'
    return 'eligible'


def coverage_ready(directory_complete, counts):
    return bool(directory_complete and counts.get('ok',0)>0 and
                not any(n for status,n in counts.items() if status not in
                        {'ok','insufficient_history','st_or_delisting','not_equity','suspended_or_stale','excluded_board'}))
