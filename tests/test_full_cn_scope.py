from data.full_cn_scope import classify_equity, coverage_ready


def test_growth_and_beijing_are_included_without_funds():
    for code in ['sh688018','sz300750','sh600519','sz000001','bj920001']:
        assert classify_equity({'ticker':code,'name':'普通股票'},scope='all_cn')=='eligible'
    assert classify_equity({'ticker':'sh510300','name':'指数ETF'})=='not_equity'
    assert classify_equity({'ticker':'sz200001','name':'B股'})=='not_equity'
    assert classify_equity({'ticker':'sh600001','name':'*ST风险'})=='st_or_delisting'


def test_full_scope_readiness_does_not_ignore_failed_or_unattempted_symbols():
    assert not coverage_ready(False,{'ok':5000})
    assert not coverage_ready(True,{'ok':5000,'error':1})
    assert not coverage_ready(True,{'ok':5000,'pending':1})
    assert coverage_ready(True,{'ok':5000,'insufficient_history':60,'st_or_delisting':100})


def test_default_scope_excludes_beijing_star_and_chinext():
    for code in ['sh688018','sz300750','sz301001','bj920001']:
        assert classify_equity({'ticker':code,'name':'普通股票'})=='excluded_board'
    for code in ['sh600519','sh603001','sh605001','sz000001','sz001001','sz002001','sz003001']:
        assert classify_equity({'ticker':code,'name':'普通股票'})=='eligible'
    assert coverage_ready(True,{'ok':3000,'excluded_board':2000})
