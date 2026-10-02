from types import SimpleNamespace
import pandas as pd
from investment.data.stock_fetcher import StockFetcher


def test_long_history_uses_full_provider_without_short_source():
    fetcher = StockFetcher.__new__(StockFetcher)
    calls = []
    frame = pd.DataFrame({"Close": [1.0, 2.0]}, index=pd.to_datetime(["2015-01-01", "2026-01-01"]))
    fetcher.yfinance = SimpleNamespace(get_history=lambda ticker, period, interval: (calls.append((ticker, period, interval)) or frame))
    assert fetcher.get_history("VICR", period="10y").equals(frame)
    assert calls == [("VICR", "10y", "1d")]


def test_long_hk_fallback_uses_explicit_dates():
    fetcher = StockFetcher.__new__(StockFetcher)
    calls = []
    fetcher.yfinance = SimpleNamespace(get_history=lambda *args: pd.DataFrame())
    frame = pd.DataFrame({"Close": [1.0]})
    fetcher.akshare = SimpleNamespace(get_hk_history=lambda ticker, **kwargs: (calls.append(kwargs) or frame))
    assert fetcher.get_history("hk00700", period="max").equals(frame)
    assert calls[0]["start_date"] == "19900101"


def test_two_year_cn_range_is_not_default_one_year():
    fetcher = StockFetcher.__new__(StockFetcher)
    counts = []
    fetcher.ashare = SimpleNamespace(get_price=lambda ticker, **kwargs: (counts.append(kwargs["count"]) or pd.DataFrame()))
    fetcher.get_history("sh600519", period="2y")
    assert counts == [500]
