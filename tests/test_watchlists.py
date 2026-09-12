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


def test_groups_form_a_tree_and_parent_group_can_hold_stocks() -> None:
    service = WatchlistService(store=InMemoryWatchlistStore(), research_service=FakeResearchService())

    service.create_group("auth0|alice", {"id": "us", "name": "美国"})
    service.create_group("auth0|alice", {"id": "finance", "name": "金融", "parent_id": "us"})
    service.create_group("auth0|alice", {"id": "banks", "name": "银行", "parent_id": "finance"})
    service.add_item("auth0|alice", "us", item("AAPL"))
    service.add_item("auth0|alice", "banks", item("JPM"))

    groups = service.get_watchlists("auth0|alice")["groups"]

    assert groups[0]["id"] == "us"
    assert groups[0]["items"][0]["ticker"] == "AAPL"
    assert groups[0]["children"][0]["children"][0]["items"][0]["ticker"] == "JPM"


def test_group_and_stock_crud_support_rename_move_and_cascade_delete() -> None:
    service = WatchlistService(store=InMemoryWatchlistStore(), research_service=FakeResearchService())
    service.create_group("auth0|alice", {"id": "us", "name": "美国"})
    service.create_group("auth0|alice", {"id": "finance", "name": "金融", "parent_id": "us"})
    service.create_group("auth0|alice", {"id": "tech", "name": "科技", "parent_id": "us"})
    service.add_item("auth0|alice", "finance", item("JPM", notes="watch"))

    service.update_group("auth0|alice", "finance", {"name": "金融服务", "parent_id": "tech"})
    service.update_item("auth0|alice", "finance", "JPM", {"notes": "core", "target_group_id": "tech"})
    groups = service.get_watchlists("auth0|alice")["groups"]

    tech = groups[0]["children"][0]
    assert tech["name"] == "科技"
    assert tech["children"][0]["name"] == "金融服务"
    assert tech["items"][0]["notes"] == "core"

    service.delete_group("auth0|alice", "tech")
    assert service.get_watchlists("auth0|alice")["groups"] == [{"id": "us", "name": "美国", "parent_id": None, "items": [], "children": []}]
