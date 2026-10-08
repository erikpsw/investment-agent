"""Regression coverage for the October 2026 reopening and Tencent factors."""
import pytest
from investment.data.formula_risk import history_timing
from investment.data.formula_scoring import score_item
from investment.data.tencent_client import TencentClient
from investment.data.ashare_client import AshareQuoteClient


@pytest.mark.parametrize("stamp", ["2026-10-08T10:11:04+08:00", "2026-10-08T02:11:04Z"])
def test_national_holiday_does_not_expire_last_trading_day(stamp):
    result = history_timing({"market": "CN", "quote_as_of": stamp}, "2026-09-30")
    assert result["status"] == "ok"
    assert result["history_lag_calendar_days"] == 8
    assert result["history_lag_trading_days"] == 1


@pytest.mark.parametrize("quote,history,expected", [
    ("2026-02-24", "2026-02-13", "ok"),
    ("2026-10-08", "2026-09-21", "stale_history"),
    ("2026-10-08", "2026-10-09", "future_history"),
    ("2027-10-08", "2027-09-30", "stale_history"),
])
def test_calendar_keeps_stale_future_and_unknown_year_guards(quote, history, expected):
    assert history_timing({"market": "CN", "quote_as_of": quote}, history)["status"] == expected


def test_makeup_weekends_are_not_exchange_sessions():
    result = history_timing({"market": "CN", "quote_as_of": "2026-10-12"}, "2026-09-30")
    assert result["status"] == "ok"
    assert result["history_lag_trading_days"] == 3


def test_holiday_preserves_shared_trend_score_and_protection():
    bars = [{"date": f"2026-09-{i:02}", "open": 100, "high": 102, "low": 98, "close": 100} for i in range(1, 25)]
    bars.append({**bars[-1], "date": "2026-09-30"})
    row = {"ticker": "sh603893", "market": "CN", "price": 100, "quote_as_of": "2026-10-08T10:11:04+08:00", "history_as_of": "2026-09-30", "risk_bars": bars,
           "change_5d": 4, "change_20d": 9, "change_60d": 12, "today_change_percent": 1, "volume_ratio": 1.4, "turnover_rate": 1.41, "pe_ratio": 83.66, "pb_ratio": 17.67, "market_cap": 87_003_000_000}
    result = score_item(row)
    assert result["data_coverage"] == 1
    assert result["missing_fields"] == []
    assert result["change_60d"] == 12
    assert result["risk_plan"]["status"] == "ok"


@pytest.mark.parametrize("parser", [TencentClient()._parse_quote, AshareQuoteClient()._parse_realtime_tx])
@pytest.mark.parametrize("pb,ratio,expected_pb,expected_ratio", [("17.67", "1.40", 17.67, 1.4), ("", "", None, None), ("--", "--", None, None), ("nan", "inf", None, None)])
def test_both_cn_quote_parsers_read_provider_pb_and_volume_ratio(parser, pb, ratio, expected_pb, expected_ratio):
    fields = [""] * 54
    for index, value in {1: "Company", 3: "205.62", 4: "215.57", 30: "20261008103548", 46: pb, 49: ratio, 53: "83.66"}.items():
        fields[index] = value
    result = parser("sh603893", 'v_sh603893="' + '~'.join(fields) + '";')
    assert result["pb_ratio"] == expected_pb
    assert result["volume_ratio"] == expected_ratio
    assert result["pb_source"] == ("Tencent" if expected_pb is not None else None)
    assert result["timestamp"] == "2026-10-08T10:35:48+08:00"


def test_optional_factors_are_missing_in_short_provider_payload():
    from investment.data.cn_quote_factors import tencent_cn_factors
    assert tencent_cn_factors([""] * 46) == {"pb_ratio": None, "volume_ratio": None, "pb_source": None, "volume_ratio_source": None}


def test_stock_detail_restores_provider_factors_and_holiday_trends(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from investment.api.routes import formula_ranking as route
    quote = {"ticker": "sh603893", "price": 100, "change_percent": 1, "market_cap": 87_003_000_000, "turnover_rate": 1.41, "pe_ratio": 83.66,
             "pb_ratio": 17.67, "volume_ratio": 1.4, "timestamp": "2026-10-08T10:11:04+08:00", "source": "Tencent"}
    monkeypatch.setattr(route, "_detail_quote", lambda _: quote)
    monkeypatch.setattr(route, "_detail_financials", AsyncMock(return_value=None))
    monkeypatch.setattr(route, "classify_instrument", lambda *_: {"instrument_type": "stock"})
    monkeypatch.setattr(route, "enrich_stock_history", lambda rows, **_: [{**rows[0], "history_as_of": "2026-09-30", "change_5d": 4, "change_20d": 9, "change_60d": 12}])
    result = asyncio.run(route.formula_stock_score("sh603893", "balanced"))["result"]
    assert result["item"]["missing_fields"] == []
    assert result["item"]["data_coverage"] == 1
    assert result["valuation"]["pb_source"] == "Tencent"
