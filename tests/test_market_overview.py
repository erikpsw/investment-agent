from investment.data.stock_fetcher import StockFetcher


EXPECTED_INDICES = [
    ("上证指数", "CN", "000001.SS"),
    ("深证成指", "CN", "399001.SZ"),
    ("创业板指", "CN", "399006.SZ"),
    ("沪深300", "CN", "000300.SS"),
    ("恒生指数", "HK", "^HSI"),
    ("恒生科技指数", "HK", "HSTECH.HK"),
    ("标普500", "US", "^GSPC"),
    ("纳斯达克综合", "US", "^IXIC"),
    ("道琼斯工业指数", "US", "^DJI"),
]


class FakeTencent:
    def get_index(self, code: str, name: str):
        return {
            "code": code,
            "name": name,
            "price": 100.0,
            "change": 1.0,
            "change_percent": 1.0,
        }


class FakeYahoo:
    def __init__(self, failed_ticker: str | None = None):
        self.failed_ticker = failed_ticker

    def get_quote(self, ticker: str):
        if ticker == self.failed_ticker:
            return {"ticker": ticker, "error": "unavailable"}
        return {
            "ticker": ticker,
            "price": 200.0,
            "change": -2.0,
            "change_percent": -1.0,
        }


def make_fetcher(failed_yahoo: str | None = None) -> StockFetcher:
    fetcher = StockFetcher.__new__(StockFetcher)
    fetcher.tencent = FakeTencent()
    fetcher.yfinance = FakeYahoo(failed_yahoo)
    return fetcher


def test_market_overview_contains_all_configured_indices():
    result = make_fetcher().get_market_overview()

    actual = [
        (item["name"], item["market"], item["history_ticker"])
        for item in result["indices"]
    ]
    assert actual == EXPECTED_INDICES
    assert result["timestamp"]


def test_market_overview_skips_only_the_failed_index():
    result = make_fetcher(failed_yahoo="HSTECH.HK").get_market_overview()

    names = [item["name"] for item in result["indices"]]
    assert "恒生科技指数" not in names
    assert len(result["indices"]) == 8
    assert "恒生指数" in names
    assert "纳斯达克综合" in names
