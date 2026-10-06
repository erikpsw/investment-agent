import asyncio
from unittest.mock import patch, AsyncMock
import pytest
from fastapi import HTTPException
from investment.api.routes import formula_ranking as module
from investment.data.formula_scoring import score_item


@pytest.fixture(autouse=True)
def default_financials_unavailable(monkeypatch):
    monkeypatch.setattr(module, "_detail_financials", AsyncMock(return_value=None))


@pytest.mark.parametrize("ticker,canonical,market", [("600519", "sh600519", "CN"), ("0700.HK", "hk00700", "HK"), ("aapl", "AAPL", "US")])
def test_detail_uses_shared_score_and_single_security_history(ticker, canonical, market):
    quote = {"ticker": canonical, "name": "Test", "price": 100, "change_percent": 2, "pe_ratio": 20, "market_cap": 1e10, "timestamp": "2026-09-30T20:00:00Z", "source": "test"}
    def enrich(rows, **kwargs):
        assert len(rows) == 1 and rows[0]["ticker"] == canonical
        assert kwargs["as_of"] == quote["timestamp"]
        return [{**rows[0], "change_5d": 3, "change_20d": 8, "change_60d": 15}]
    with patch.object(module, "_detail_quote", return_value=quote), patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "enrich_stock_history", side_effect=enrich), patch.object(module, "enrich_foreign_history", side_effect=enrich):
        result = asyncio.run(module.formula_stock_score(ticker, "conservative"))["result"]
    assert result["item"]["ticker"] == canonical
    assert result["item"]["market"] == market
    assert result["item"]["formula_score"] == score_item(result["item"], "conservative")["formula_score"]
    assert result["item"]["today_change_percent"] == 2
    assert result["item"]["change_5d"] == 3
    assert result["item"]["change_20d"] == 8
    assert result["item"]["change_60d"] == 15
    assert "volume_ratio" in result["item"]["missing_fields"]


def test_detail_does_not_score_etfs_or_unavailable_prices():
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "etf"}), patch.object(module, "_detail_quote") as quote:
        assert asyncio.run(module.formula_stock_score("SPY", "balanced"))["result"]["status"] == "not_supported"
        quote.assert_not_called()
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "_detail_quote", return_value={"price": None}):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(module.formula_stock_score("AAPL", "balanced"))
        assert exc.value.status_code == 503


def test_detail_refuses_wrong_security_and_leaves_failed_history_missing():
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "_detail_quote", return_value={"ticker": "MSFT", "price": 100}):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(module.formula_stock_score("AAPL", "balanced"))
        assert exc.value.status_code == 503
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "_detail_quote", return_value={"ticker": "AAPL", "price": 100}), patch.object(module, "enrich_foreign_history", side_effect=RuntimeError("offline")):
        item = asyncio.run(module.formula_stock_score("AAPL", "balanced"))["result"]["item"]
    assert item["recommendation"] == "数据不足"
    assert item["change_5d"] is None
    assert item["risk_plan"]["status"] != "ok"


def test_detail_rejects_invalid_identifiers_before_provider_requests():
    with patch.object(module, "_detail_quote") as quote:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(module.formula_stock_score("../invalid", "balanced"))
        assert exc.value.status_code == 422
        quote.assert_not_called()


def test_detail_hk_provider_timestamp_is_interpreted_in_market_timezone():
    from investment.data.quote_timing import quote_time_fields
    seen = []
    def enrich(rows, **kwargs):
        seen.append(kwargs["as_of"])
        return rows
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "_detail_quote", return_value={"ticker": "hk00700", "price": 100, **quote_time_fields("20260930160000", "HK")}), patch.object(module, "enrich_foreign_history", side_effect=enrich):
        response = asyncio.run(module.formula_stock_score("hk00700", "balanced"))["result"]
    assert seen == ["2026-09-30T16:00:00+08:00"]
    assert response["quote_as_of"] == seen[0]


@pytest.mark.parametrize("ticker,market", [("sh600519", "CN"), ("hk00700", "HK"), ("AAPL", "US")])
@pytest.mark.parametrize("stamp,status", [("2026-09-30T16:00:00", None), ("20260930160000", None), ("2026-09-30", None), (1790971200, None), ("2026-09-30T16:00:00+08:00", "unverified_timezone"), ("2026-09-30T16:00:00+08:00", "unavailable")])
def test_detail_never_guesses_or_overrides_unverified_quote_timezone(ticker, market, stamp, status):
    seen = []
    def enrich(rows, **kwargs):
        seen.append(kwargs["as_of"])
        return rows
    quote = {"ticker": ticker, "price": 100, "timestamp": stamp, "timestamp_status": status, "fetched_at": "2026-10-04T03:00:00+00:00"}
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "_detail_quote", return_value=quote), patch.object(module, "enrich_stock_history", side_effect=enrich), patch.object(module, "enrich_foreign_history", side_effect=enrich):
        result = asyncio.run(module.formula_stock_score(ticker, "balanced"))["result"]
    assert seen == [None] and result["quote_as_of"] is None
    assert result["fetched_at"] == quote["fetched_at"]


def test_detail_keeps_unknown_quote_timezone_separate_from_fetch_time():
    quote = {"ticker": "AAPL", "price": 100, "timestamp": None, "timestamp_status": "unverified_timezone", "provider_timestamp_raw": "2026-10-03 09:30:15", "fetched_at": "2026-10-04T03:00:00+00:00"}
    seen = []
    def enrich(rows, **kwargs):
        seen.append(kwargs["as_of"])
        return rows
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "_detail_quote", return_value=quote), patch.object(module, "enrich_foreign_history", side_effect=enrich):
        result = asyncio.run(module.formula_stock_score("AAPL", "balanced"))["result"]
    assert seen == [None] and result["quote_as_of"] is None
    assert result["quote_time_status"] == "unverified_timezone"
    assert result["provider_timestamp_raw"] == quote["provider_timestamp_raw"]
    assert result["fetched_at"] == quote["fetched_at"]


@pytest.mark.parametrize("pe", [20, None])
def test_detail_financial_valuation_follows_ttm_null_and_pb_policy(pe):
    financials = {"ticker": "AAPL", "pe_ratio": pe, "pb_ratio": 3, "pe_basis": "TTM", "source": "financial"}
    with patch.object(module, "classify_instrument", return_value={"instrument_type": "stock"}), patch.object(module, "_detail_quote", return_value={"ticker": "AAPL", "price": 100, "pe_ratio": 40}), patch.object(module, "_detail_financials", AsyncMock(return_value=financials)), patch.object(module, "enrich_foreign_history", side_effect=lambda rows, **kw: rows):
        result = asyncio.run(module.formula_stock_score("AAPL", "balanced"))["result"]
    assert result["item"]["pe_ratio"] == pe
    assert result["item"]["pb_ratio"] == 3
    assert result["valuation"]["pe_source"] == "financial"
    assert result["financials_status"] == "available"
