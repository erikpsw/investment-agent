import pytest
from data.momentum_visual import chart_payload


def bars():
    return [dict(date=d,open=10,high=11,low=9,close=10,volume=100) for d in ['2024-01-02','2024-01-03']]


def test_markers_are_original_simulated_fills_on_hfq_basis_only():
    trade=dict(code='sz000001',entry_date='2024-01-02',exit_date='2024-01-03',entry_price=10,exit_price=9)
    p=chart_payload('sz000001','平安银行',bars(),[trade])
    assert p['price_basis']=='hfq' and p['trades']==[trade]
    assert p['series_kind']=='archived_research_not_actual_fills'
    assert chart_payload('sh600000','浦发',bars(),[trade])['trades']==[]


def test_missing_bar_or_reversed_trade_is_not_fabricated():
    with pytest.raises(ValueError):
        chart_payload('sz000001','平安',bars(),[dict(code='sz000001',entry_date='2024-01-01',exit_date='2024-01-03')])
    with pytest.raises(ValueError):
        chart_payload('sz000001','平安',list(reversed(bars())),[])
