import pytest
from data.weekly_entry_risk import check_entry_risk


def preview():
    return {'mapping_status':'compatible','native_open':10.2,'native_stop':9.8,
            'signal_at':'2024-01-02','executable_from':'2024-01-03','execution_ready':False}


def test_predefined_gap_and_stop_limits_accept_price_risk_only():
    r=check_entry_risk(preview(),{'date':'2024-01-02','close':10.,'atr14':.5,'price_basis':'unadjusted'})
    assert r['price_risk_passed'] is True
    assert r['execution_ready'] is False
    assert r['gap_atr']==pytest.approx(.4)


def test_confirmed_real_case_fails_existing_thresholds():
    p=preview();p.update(native_open=6.71,native_stop=5.93)
    r=check_entry_risk(p,{'date':'2024-01-02','close':6.49,'atr14':.29809362769903563,'price_basis':'unadjusted'})
    assert r['price_risk_passed'] is False
    assert set(r['reasons'])=={'gap_exceeds_0.5_atr','stop_distance_exceeds_2.5_atr'}


@pytest.mark.parametrize('changes',[{'price_basis':'hfq'},{'date':'2024-01-03'},{'atr14':None},{'atr14':float('nan')}])
def test_unknown_or_future_reference_blocks(changes):
    ref={'date':'2024-01-02','close':10.,'atr14':.5,'price_basis':'unadjusted'};ref.update(changes)
    assert check_entry_risk(preview(),ref)['price_risk_passed'] is False
