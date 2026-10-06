"""Reviewed ordinary-share market-cap reference only; never infers profit/book allocation."""
import copy
from datetime import date, timedelta
from investment.data.formula_fundamentals import _known, _day
from investment.data.formula_scoring import number


def attach_cap_reference(bars, facts):
    for fact in facts:
        end, filed = _day(fact.get('end')), _day(fact.get('filed'))
        value = number(fact.get('value'))
        if end is None or filed is None or end > filed or fact.get('available') != (filed + timedelta(days=1)).isoformat() or value is None or value <= 0:
            raise ValueError('Invalid reviewed share fact')
    result = []; previous_scale = None; last_split = None
    for original in bars:
        row = copy.deepcopy(original); current = _day(row.get('date'))
        if current is None:
            raise ValueError('Invalid historical bar date')
        scale = number(row.get('share_scale'))
        if scale is not None and scale > 0:
            if previous_scale is not None and abs(scale / previous_scale - 1) > .2:
                last_split = row['date']
            previous_scale = scale
        if number(row.get('market_cap')) is None:
            if any(number(row.get(field)) is not None for field in ('pe_ratio', 'pb_ratio')):
                raise ValueError('Orphan valuation ratios cannot be retimed by a cap reference')
            known = _known(facts, row['date'])
            selected = max(known, key=lambda f: f['end'], default=None)
            price = number(row.get('raw_close'))
            if selected and selected['value'] is not None and price is not None and price > 0 and \
                (current - date.fromisoformat(selected['end'])).days <= 400 and \
                (last_split is None or selected['end'] >= last_split) and number(price * selected['value']) is not None:
                row.update(market_cap=price * selected['value'], metrics_as_of=selected['available'],
                    fundamentals_source='SEC reviewed cover ordinary-share market-cap reference only',
                    shares_period_end=selected['end'], fundamentals_accessions=[selected['accession']],
                    cover_share_reference=True, cover_share_fields=['market_cap'])
        result.append(row)
    return result
