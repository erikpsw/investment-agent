from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

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

    def get_quote(self, ticker: str):
        return {
            "ticker": ticker,
            "price": float(self.history.iloc[-1]["close"]),
            "change_percent": 1.25,
            "volume": 5000,
            "currency": "CNY",
        }

    def get_history(self, ticker: str, period: str = "2y", interval: str = "1d"):
        assert period == "2y"
        assert interval == "1d"
        return self.history.copy()


def make_service(closes: list[float]) -> ResearchSnapshotService:
    return ResearchSnapshotService(
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
    assert result["returns"]["20d"] == pytest.approx(
        (360 / 340 - 1) * 100, abs=0.0001
    )
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


def test_snapshot_keeps_partial_results_when_history_and_news_fail() -> None:
    class PartialFetcher(FakeFetcher):
        def get_history(self, ticker: str, period: str = "2y", interval: str = "1d"):
            raise RuntimeError("history unavailable")

    service = ResearchSnapshotService(
        fetcher=PartialFetcher([10.0]),
        news_provider=lambda **_: (_ for _ in ()).throw(RuntimeError("news unavailable")),
    )

    result = service.snapshot("AAPL", "Apple", "US")

    assert result["quote"]["price"] == 10.0
    assert result["returns"]["5d"] is None
    assert result["recent_news"] == []
    assert result["errors"] == ["history: history unavailable", "news: news unavailable"]
