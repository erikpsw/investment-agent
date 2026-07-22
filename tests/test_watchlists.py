from __future__ import annotations

import pytest

from investment.data.watchlist_store import InMemoryWatchlistStore
from investment.data.watchlists import WatchlistGroupNotFound, WatchlistService


def item(ticker: str, name: str = "Example", market: str = "US", notes: str = ""):
    return {"ticker": ticker, "name": name, "market": market, "notes": notes}


class FakeResearchService:
    def __init__(self) -> None:
        self.include_history_calls: list[bool] = []

    def enrich(self, items, include_history=False):
        self.include_history_calls.append(include_history)
        return [
            {
                **entry,
                "research": {
                    "returns": {"5d": 1.2, "20d": 3.4, "60d": None, "250d": None},
                    "history": [{"time": "2026-07-21", "close": 100}]
                    if include_history
                    else None,
                },
            }
            for entry in items
        ]


def test_same_group_deduplicates_but_cross_group_duplicate_is_preserved() -> None:
    service = WatchlistService(
        store=InMemoryWatchlistStore(),
        research_service=FakeResearchService(),
    )

    saved = service.save_watchlists(
        "auth0|alice",
        [
            {"id": "core", "name": "Core", "items": [item("AAPL"), item("aapl")]},
            {"id": "tech", "name": "Tech", "items": [item("AAPL")]},
        ],
    )

    assert [len(group["items"]) for group in saved["groups"]] == [1, 1]
    assert saved["groups"][0]["items"][0]["ticker"] == "AAPL"
    assert saved["groups"][1]["items"][0]["ticker"] == "AAPL"


def test_group_order_and_item_order_are_preserved() -> None:
    service = WatchlistService(
        store=InMemoryWatchlistStore(),
        research_service=FakeResearchService(),
    )

    saved = service.save_watchlists(
        "auth0|alice",
        [
            {"id": "second", "name": "Second", "items": [item("MSFT"), item("AAPL")]},
            {"id": "first", "name": "First", "items": []},
        ],
    )

    assert [group["id"] for group in saved["groups"]] == ["second", "first"]
    assert [entry["ticker"] for entry in saved["groups"][0]["items"]] == ["MSFT", "AAPL"]


def test_get_watchlists_filters_group_and_forwards_history_flag() -> None:
    store = InMemoryWatchlistStore()
    research = FakeResearchService()
    service = WatchlistService(store=store, research_service=research)
    store.save(
        "auth0|alice",
        [
            {"id": "core", "name": "Core", "items": [item("AAPL")]},
            {"id": "hk", "name": "Hong Kong", "items": [item("hk00700", "腾讯控股", "HK")]},
        ],
    )

    result = service.get_watchlists(
        "auth0|alice", group_id="hk", include_history=True
    )

    assert [group["id"] for group in result["groups"]] == ["hk"]
    assert result["groups"][0]["items"][0]["research"]["history"]
    assert research.include_history_calls == [True]


def test_unknown_group_raises_domain_error() -> None:
    service = WatchlistService(
        store=InMemoryWatchlistStore(),
        research_service=FakeResearchService(),
    )

    with pytest.raises(WatchlistGroupNotFound):
        service.get_watchlists("auth0|alice", group_id="missing")
