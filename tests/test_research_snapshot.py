from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from investment.data.market_cache import MarketDataCache
from investment.data.research_snapshot import ResearchSnapshotService


def history_for(closes: list[float]) -> pd.DataFrame:
    start = datetime(2025, 1, 1)
    return pd.DataFrame(
        {
            "time": [(start + timedelta(days=index)).date().isoformat() for index in range(len(closes))],
            "open": [value - 0.5 for value in closes],
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "volume": [1000 + index * 10 for index in range(len(closes))],
        }
    )


class FakeFetcher:
    def __init__(self, closes: list[float]) -> None:
        self.history = history_for(closes)
        self.history_calls = 0

    def get_quote(self, ticker: str):
        return {
            "ticker": ticker,
            "price": float(self.history.iloc[-1]["close"]),
            "change_percent": 1.25,
            "volume": 5000,
            "currency": "CNY",
        }

    def get_history(self, ticker: str, period: str = "2y", interval: str = "1d"):
        assert period in {"2y", "1mo"}
        assert interval == "1d"
        self.history_calls += 1
        return self.history.copy()


def make_service(closes: list[float]) -> ResearchSnapshotService:
    return ResearchSnapshotService(
        market_cache=MarketDataCache(),
        fetcher=FakeFetcher(closes),
        news_provider=lambda **_: [
            {
                "title": "Example news",
                "published": "2026-07-22T09:00:00+08:00",
                "source": "Example",
                "link": "https://example.com/news",
                "summary": "Source summary",
            }
        ],
    )


def test_snapshot_returns_structured_metrics_without_history_by_default() -> None:
    service = make_service([float(value) for value in range(100, 361)])

    result = service.snapshot("sh600000", "浦发银行", "CN")

    assert result["returns"]["5d"] == pytest.approx(
        (360 / 355 - 1) * 100, abs=0.0001
    )
    assert result["returns"]["10d"] == pytest.approx(
        (360 / 350 - 1) * 100, abs=0.0001
    )
    assert result["returns"]["20d"] == pytest.approx(
        (360 / 340 - 1) * 100, abs=0.0001
    )
    assert result["moving_averages"]["ma10"] == pytest.approx(355.5)
    assert result["moving_averages"]["ma20"] == pytest.approx(
        sum(range(341, 361)) / 20
    )
    assert result["history"] is None
    assert result["technical"]["volatility_20d"] is not None
    assert result["technical"]["rsi14"] == 100.0
    assert result["technical"]["max_drawdown_250d"] == 0.0
    assert result["recent_news"][0]["title"] == "Example news"
    assert result["errors"] == []


def test_snapshot_requires_n_plus_one_closes_for_n_day_return() -> None:
    result = make_service([float(value) for value in range(1, 21)]).snapshot(
        "AAPL", "Apple", "US"
    )

    assert result["returns"]["5d"] is not None
    assert result["returns"]["20d"] is None
    assert result["moving_averages"]["ma20"] == pytest.approx(10.5)
    assert result["moving_averages"]["ma60"] is None


def test_snapshot_optionally_returns_at_most_250_ascending_bars() -> None:
    result = make_service([float(value) for value in range(1, 301)]).snapshot(
        "AAPL", "Apple", "US", include_history=True
    )

    assert len(result["history"]) == 250
    assert result["history"][0]["time"] < result["history"][-1]["time"]
    assert result["history"][0]["close"] == 51.0
    assert result["history"][-1]["close"] == 300.0


def test_enrich_preserves_input_order_and_attaches_research() -> None:
    service = make_service([float(value) for value in range(1, 80)])

    result = service.enrich(
        [
            {"ticker": "AAPL", "name": "Apple", "market": "US"},
            {"ticker": "hk00700", "name": "腾讯控股", "market": "HK"},
        ]
    )

    assert [item["ticker"] for item in result] == ["AAPL", "hk00700"]
    assert all("research" in item for item in result)


def test_quote_adds_five_day_change_volume_and_caches_history() -> None:
    fetcher = FakeFetcher([100.0, 101.0, 102.0, 103.0, 104.0, 110.0])
    service = ResearchSnapshotService(fetcher=fetcher, news_provider=lambda **_: [], market_cache=MarketDataCache())
    item = {"ticker": "AAPL", "name": "Apple", "market": "US"}

    first = service.quote(item)
    second = service.quote(item)

    quote = first["research"]["quote"]
    assert quote["day_change_percent"] == pytest.approx(1.25)
    assert quote["five_day_change_percent"] == pytest.approx(10.0)
    assert quote["five_day_asof"] == "2025-01-06"
    assert quote["volume"] == 5000
    assert quote["fetched_at"]
    assert second["research"]["quote"]["five_day_change_percent"] == pytest.approx(10.0)
    assert fetcher.history_calls == 1


def test_quote_enrichment_batches_quotes_without_history_or_news() -> None:
    class QuoteOnlyFetcher(FakeFetcher):
        def __init__(self) -> None:
            super().__init__([10.0])
            self.history_calls = 0

        def get_history(self, *args, **kwargs):
            return super().get_history(*args, **kwargs)

        def get_quotes(self, items):
            return {item["ticker"]: self.get_quote(item["ticker"]) for item in items}

    fetcher = QuoteOnlyFetcher()
    service = ResearchSnapshotService(fetcher=fetcher, news_provider=lambda **_: pytest.fail("news should not load"), market_cache=MarketDataCache())

    result = service.enrich_quotes([
        {"ticker": "AAPL", "name": "Apple", "market": "US"},
        {"ticker": "sh600000", "name": "浦发银行", "market": "CN"},
    ])

    assert [item["research"]["quote"]["price"] for item in result] == [10.0, 10.0]
    assert fetcher.history_calls == 0



def test_snapshot_keeps_partial_results_when_history_and_news_fail() -> None:
    class PartialFetcher(FakeFetcher):
        def get_history(self, ticker: str, period: str = "2y", interval: str = "1d"):
            raise RuntimeError("history unavailable")

    service = ResearchSnapshotService(
        market_cache=MarketDataCache(),
        fetcher=PartialFetcher([10.0]),
        news_provider=lambda **_: (_ for _ in ()).throw(RuntimeError("news unavailable")),
    )

    result = service.snapshot("AAPL", "Apple", "US")

    assert result["quote"]["price"] == 10.0
    assert result["returns"]["5d"] is None
    assert result["recent_news"] == []
    assert result["errors"] == ["history: history unavailable", "news: news unavailable"]


def test_full_research_is_cached_after_market_close() -> None:
    class CountingFetcher(FakeFetcher):
        def __init__(self) -> None:
            super().__init__([10.0, 11.0])
            self.history_calls = 0

        def get_history(self, *args, **kwargs):
            return super().get_history(*args, **kwargs)

    fetcher = CountingFetcher()
    service = ResearchSnapshotService(fetcher=fetcher, news_provider=lambda **_: [], market_cache=MarketDataCache())

    service.snapshot("sh600000", "浦发银行", "CN", include_history=True)
    service.snapshot("sh600000", "浦发银行", "CN", include_history=True)

    assert fetcher.history_calls == 1


def test_snapshot_ignores_legacy_research_cache_without_new_metrics() -> None:
    cache = MarketDataCache()
    cache.set("US", "AAPL", "research", {"returns": {"5d": 1.0}})
    service = ResearchSnapshotService(
        fetcher=FakeFetcher([float(value) for value in range(1, 21)]),
        news_provider=lambda **_: [],
        market_cache=cache,
    )

    result = service.snapshot("AAPL", "Apple", "US")

    assert result["returns"]["10d"] == pytest.approx((20 / 10 - 1) * 100)


def test_enrich_reads_cached_research_in_one_batch() -> None:
    class CountingStore:
        def __init__(self) -> None:
            self.load_calls = 0
            self.entries = {}

        def load(self, keys):
            self.load_calls += 1
            return {key: self.entries[key] for key in keys if key in self.entries}

        def save(self, key, value, fetched_at):
            self.entries[key] = (value, fetched_at)

    store = CountingStore()
    cache = MarketDataCache(store=store)
    first = ResearchSnapshotService(
        fetcher=FakeFetcher([10.0, 11.0]),
        news_provider=lambda **_: [],
        market_cache=cache,
    )
    first.snapshot("AAPL", "Apple", "US", include_history=True)
    first.snapshot("MSFT", "Microsoft", "US", include_history=True)

    restored = ResearchSnapshotService(
        fetcher=FakeFetcher([10.0, 11.0]),
        news_provider=lambda **_: pytest.fail("cached research should not fetch"),
        market_cache=MarketDataCache(store=store),
    )
    result = restored.enrich([
        {"ticker": "AAPL", "name": "Apple", "market": "US"},
        {"ticker": "MSFT", "name": "Microsoft", "market": "US"},
    ], include_history=True)

    assert [item["research"]["quote"]["price"] for item in result] == [11.0, 11.0]
    assert store.load_calls == 3  # two setup writes/read misses + one bulk restored read


def test_opening_details_after_summary_cache_still_has_history() -> None:
    service = make_service([float(value) for value in range(1, 30)])
    assert service.snapshot("AAPL", "Apple", "US")["history"] is None
    assert len(service.snapshot("AAPL", "Apple", "US", include_history=True)["history"]) == 29


def test_detail_sources_are_queried_concurrently() -> None:
    from threading import Barrier
    ready = Barrier(3)
    class ConcurrentFetcher(FakeFetcher):
        def get_quote(self, ticker):
            ready.wait(timeout=2)
            return super().get_quote(ticker)
        def get_history(self, *args, **kwargs):
            ready.wait(timeout=2)
            return super().get_history(*args, **kwargs)
    def news(**kwargs):
        ready.wait(timeout=2)
        return []
    service = ResearchSnapshotService(fetcher=ConcurrentFetcher([10, 11]), news_provider=news, market_cache=MarketDataCache())
    result = service.snapshot("AAPL", "Apple", "US", include_history=True)
    assert result["errors"] == []
    assert result["quote"]["price"] == 11
    assert len(result["history"]) == 2
