"""Isolated reviewed cover-share reference adapter; no runtime/default ledger changes."""
from bisect import bisect_right
import copy
from investment.data.formula_fundamentals import _known


def merge_points(base, shares, *, transition):
    original = sorted(base, key=lambda p: p['available'])
    if len({p['available'] for p in original}) != len(original):
        raise ValueError('Duplicate original ledger dates')
    days = sorted({p['available'] for p in original} | {s['available'] for s in shares} | {transition})
    dates = [p['available'] for p in original]
    points = []
    for current in days:
        index = bisect_right(dates, current) - 1
        if index < 0:
            continue  # No original income/book ledger context yet.
        point = copy.deepcopy(original[index]); point['available'] = current
        if point.get('shares') is None:
            known = _known(shares, current)
            selected = max(known, key=lambda s: s['end'], default=None)
            if selected and (current < transition or selected['end'] >= transition):
                point['shares'] = copy.deepcopy(selected)
                point['source'] = 'SEC reviewed DEI cover-share reference + original us-gaap ledger'
                point['cover_share_reference'] = True
                point['historical_mapping_complete'] = False
        points.append(point)
    return points
