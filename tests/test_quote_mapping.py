import asyncio
from types import SimpleNamespace
import pytest
from investment.data.sina_client import SinaClient
from investment.data.tencent_client import TencentClient
from investment.data.ashare_client import AshareQuoteClient
from investment.api.routes import financials, quotes


def test_sina_us_eps_is_not_pe_and_average_volume_is_not_amount():
    fields = ["0"] * 27
    for index, value in {0: "Vicor Corporation", 1: "288.94", 11: "862867", 12: "13322079144", 13: "3.03", 14: "95.36", 26: "290.68"}.items(): fields[index] = value
    result = SinaClient()._parse_us_quote("VICR", 'var hq_str_gb_vicr="' + ','.join(fields) + '";')
    assert result["eps"] == 3.03
    assert result["pe_ratio"] == 95.36
    assert result["amount"] is None
    assert result["average_volume"] == 862867
    assert result["pe_source"] == "Sina"


def test_sina_hk_open_and_close_match_price_change():
    fields = ["0"] * 19
    for index, value in {0: "TENCENT", 1: "腾讯控股", 2: "430", 3: "432", 6: "431", 7: "-1", 8: "-0.23", 13: "15.664"}.items(): fields[index] = value
    result = SinaClient()._parse_hk_quote("hk00700", 'var hq_str_rt_hk00700="' + ','.join(fields) + '";')
    assert result["open"] == 430
    assert result["prev_close"] == 432
    assert result["price"] - result["prev_close"] == result["change"]


def tencent_fixture(code):
    fields = ["0"] * 54
    for index, value in {1: "Company", 3: "431", 4: "432", 5: "430", 6: "38331", 31: "-1", 32: "-0.23", 37: "479725", 39: "19.32", 45: "15733.78", 52: "17.67", 53: "19.11"}.items(): fields[index] = value
    return 'v_' + code + '="' + '~'.join(fields) + '";'


def test_tencent_hk_change_uses_percent_field():
    result = TencentClient()._parse_hk_quote("hk00700", tencent_fixture("hk00700"))
    assert result["change_percent"] == -0.23
    assert result["open"] == 430
    assert result["market_cap"] == pytest.approx(15733.78 * 1e8)


def test_cn_ttm_pe_and_units_are_consistent_for_both_parsers():
    text = tencent_fixture("sh600519")
    for result in [TencentClient()._parse_quote("sh600519", text), AshareQuoteClient()._parse_realtime_tx("sh600519", text)]:
        assert result["pe_ratio"] == 19.11
        assert result["pe_basis"] == "TTM"
        assert result["market_cap"] == pytest.approx(15733.78 * 1e8)
        assert result["volume"] == 3833100
        assert result["amount"] == 4797250000


def test_financials_preserves_yahoo_ttm_and_missing_pe(monkeypatch):
    for pe in [92.60898, None, 0.0]:
        monkeypatch.setattr(financials, "fetcher", SimpleNamespace(get_key_metrics=lambda _: {"name": "Vicor", "pe_ratio": pe, "eps": 3.12, "pe_basis": "TTM", "pe_source": "Yahoo Finance"}, get_quote=lambda _: {"pe_ratio": 95.36, "eps": 3.03, "pe_source": "Sina"}))
        result = asyncio.run(financials.get_financials("VICR"))
        assert result.pe_ratio == pe
        assert result.eps == 3.12
        assert result.pe_source == "Yahoo Finance"


def test_market_detection_includes_hk_suffix():
    assert quotes._detect_market("0700.HK") == "HK"
    assert quotes._detect_market("sh600519") == "CN"
    assert quotes._detect_market("VICR") == "US"


def test_cn_percentage_points_and_yahoo_fractions_share_api_units():
    assert financials._ratio_metric({"净资产收益率(%)": 25}, "roe", "净资产收益率") == 0.25
    assert financials._ratio_metric({"roe": 0.25}, "roe", "净资产收益率") == 0.25
    assert financials._ratio_metric({"roe": "25%"}, "roe", "净资产收益率") == 0.25
