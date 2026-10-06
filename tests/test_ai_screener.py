import asyncio
import math
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from investment.api.routes import ai_screener as screener


@pytest.fixture(autouse=True)
def no_history_network(monkeypatch):
    for name in ("enrich_stock_history", "enrich_foreign_history"):
        monkeypatch.setattr(screener, name, lambda rows, **kwargs: rows, raising=False)


@pytest.mark.parametrize("market", ["CN", "HK", "US"])
def test_history_is_enriched_for_all_matches_before_display_limit(monkeypatch, market):
    rows = [{"ticker": f"T{i}", "market": market, "pe_ratio": 10, "price": 100} for i in range(125)]
    scan = {"rows": rows, "generated_at": "2026-09-25"}
    monkeypatch.setattr(screener, "scan_cn_market", lambda: scan)
    monkeypatch.setattr(screener, "scan_foreign_market", lambda _: scan)
    called = []
    def enrich(values, **kwargs):
        assert len(values) == kwargs["limit"] == (120 if market == "US" else 125)
        assert kwargs["as_of"] == "2026-09-25"
        called.append(market)
        return [{**v, "change_5d": 2, "change_20d": 8, "change_60d": 10 if v["ticker"] == "T124" else -20, "history_as_of": "2026-09-25"} for v in values]
    monkeypatch.setattr(screener, "enrich_stock_history" if market == "CN" else "enrich_foreign_history", enrich)
    plan = screener.ScreenPlan(summary="PE", filters=[screener.Condition(field="pe_ratio", op="lt", value=20)])
    result = screener.execute(plan, 1, market)
    assert called == [market]
    assert result["matched_count"] == result["history_requested_count"] == (120 if market == "US" else 125)
    if market == "US":
        assert result['history_deferred_count'] == 5 and result['snapshot_matched_count'] == 125
    assert result["items"][0]["ticker"] == "T124"
    assert result["items"][0]["contributions"]["20日趋势"] > 0


def test_historical_filters_ignore_snapshot_values_and_refuse_stale_history(monkeypatch):
    rows = [{"ticker": name, "market": "US", "price": 100, "change_60d": value} for name, value in [("NEW", None), ("FAILED", 99), ("STALE", 99)]]
    monkeypatch.setattr(screener, "scan_foreign_market", lambda _: {"rows": rows, "generated_at": "2026-09-25"})
    def enrich(values, **kwargs):
        assert len(values) == 3
        assert all(v.get("change_60d") is None for v in values)
        return [{**v, **({"change_5d": 3, "change_20d": 10, "change_60d": 15, "history_as_of": "2026-09-25" if v["ticker"] == "NEW" else "2026-09-01"} if v["ticker"] != "FAILED" else {})} for v in values]
    monkeypatch.setattr(screener, "enrich_foreign_history", enrich)
    plan = screener.ScreenPlan(summary="历史", filters=[screener.Condition(field="change_60d", op="gt", value=10)])
    result = screener.execute(plan, 20, "US")
    assert [v["ticker"] for v in result["items"]] == ["NEW"]
    assert result["filter_coverage"]["change_60d"] == {"available": 1, "total": 3}


def test_five_and_twenty_day_explicit_conditions_are_supported():
    plan = screener.explicit_plan("5日涨幅大于0%且20日涨幅不超过15%")
    assert [c.field for c in plan.filters] == ["change_5d", "change_20d"]


def test_schema_rejects_unknown_fields_and_nonfinite_bounds():
    for field, value in [("roe", 20), ("pe_ratio", math.inf)]:
        with pytest.raises(ValidationError):
            screener.Condition(field=field, op="lte", value=value)


def test_missing_and_nonfinite_metrics_do_not_match():
    condition = screener.Condition(field="pe_ratio", op="lte", value=20)
    for value in [None, math.nan, math.inf, True, "10"]:
        assert not screener.match({"pe_ratio": value}, condition)
    assert screener.match({"pe_ratio": 20}, condition)
    assert not screener.match({"pe_ratio": 20.1}, condition)


def test_filter_coverage_distinguishes_missing_data_from_no_matches():
    plan = screener.ScreenPlan(summary="量比", filters=[screener.Condition(field="volume_ratio", op="gte", value=2)])
    rows = [{"volume_ratio": value} for value in [None, math.nan, math.inf, True, "10", 1]]
    with patch.object(screener, "scan_foreign_market", return_value={"rows": rows}):
        result = screener.execute(plan, 20, "US")
    assert result["items"] == []
    assert result["filter_coverage"] == {"volume_ratio": {"available": 1, "total": 6}}


def test_screen_filters_full_universe_before_limiting():
    rows = [{"ticker": f"sh{i:06}", "name": "测试", "pe_ratio": pe, "pb_ratio": 2, "market_cap": 20_000_000_000} for i, pe in enumerate([-5, None, 10, 15, 35])]
    plan = screener.ScreenPlan.model_validate(screener.PRESETS["value"])
    with patch.object(screener, "scan_cn_market", return_value={"rows": rows, "generated_at": "2026-10-01", "cached": True}):
        result = screener.execute(plan, 1)
    assert result["scanned_count"] == 5
    assert result["matched_count"] == 2
    assert len(result["items"]) == 1
    assert len(result["items"][0]["match_reasons"]) == 5


def test_unsupported_conditions_do_not_execute_partial_screen():
    plan = screener.ScreenPlan(summary="高ROE", filters=[], unsupported=["ROE数据不可用"])
    with patch.object(screener, "interpret", return_value=plan), patch.object(screener, "execute") as execute:
        result = asyncio.run(screener.screen(screener.ScreenRequest(query="ROE大于20%")))
    assert result["status"] == "needs_revision"
    execute.assert_not_called()


def test_presets_do_not_call_ai():
    with patch.object(screener, "interpret") as interpret, patch.object(screener, "execute", return_value={"items": []}):
        result = asyncio.run(screener.screen(screener.ScreenRequest(query="模板", preset="value")))
    assert result["status"] == "ok"
    interpret.assert_not_called()


def test_numeric_fallback_keeps_bounds_units_and_does_not_ignore_unknown_text():
    plan = screener.explicit_plan("市盈率大于0且小于20，总市值大于100亿元")
    assert len(plan.filters) == 3
    assert plan.filters[2].value == 10_000_000_000
    assert screener.explicit_plan("市盈率小于20，ROE大于20%") is None
    assert screener.explicit_plan("市盈率小于20或者市值大于100亿元") is None
    assert screener.explicit_plan("市盈率大于1亿元") is None


@pytest.mark.parametrize('market,currency', [('HK','HKD'),('US','USD')])
def test_foreign_screen_uses_stock_pool_and_native_currency(market,currency):
    plan=screener.ScreenPlan(summary='value',filters=[screener.Condition(field='market_cap',op='gte',value=100)])
    with patch.object(screener,'scan_foreign_market',return_value={'rows':[{'ticker':'TEST','market':market,'market_cap':200}], 'source':'snapshot'}), patch.object(screener,'scan_cn_market') as cn:
        r=screener.execute(plan,20,market)
    cn.assert_not_called()
    assert r['currency']==currency and r['items'][0]['market']==market
    assert currency in r['items'][0]['match_reasons'][0]


def test_conflicting_currency_does_not_execute_or_call_ai():
    with patch.object(screener,'execute') as execute, patch.object(screener,'interpret') as interpret:
        r=asyncio.run(screener.screen(screener.ScreenRequest(query='市值大于100亿美元',market='HK')))
    assert r['status']=='needs_revision'
    execute.assert_not_called(); interpret.assert_not_called()
    assert screener.explicit_plan('港股市值大于100亿港元').filters[0].value==10_000_000_000
    assert screener.explicit_plan('美股成交额大于5万美元').filters[0].value==50_000
