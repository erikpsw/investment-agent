from __future__ import annotations

from datetime import datetime

from investment.data.market_cache import MarketDataCache, is_market_open


def test_cn_quotes_are_reused_after_market_close() -> None:
    cache = MarketDataCache()
    cache.set("CN", "sh600000", "quote", {"price": 10.0}, datetime(2026, 9, 11, 15, 1))

    assert cache.get("CN", "sh600000", "quote", datetime(2026, 9, 11, 21, 0)) == {"price": 10.0}


def test_cn_quote_cache_expires_during_open_market() -> None:
    cache = MarketDataCache(quote_ttl_seconds=15)
    cache.set("CN", "sh600000", "quote", {"price": 10.0}, datetime(2026, 9, 11, 9, 30))

    assert cache.get("CN", "sh600000", "quote", datetime(2026, 9, 11, 9, 30, 16)) is None


def test_market_hours_respect_local_market_sessions() -> None:
    assert is_market_open("CN", datetime(2026, 9, 11, 10, 0))
    assert not is_market_open("CN", datetime(2026, 9, 11, 12, 0))
    assert not is_market_open("CN", datetime(2026, 9, 11, 21, 0))
    assert not is_market_open("CN", datetime(2026, 9, 12, 10, 0))


def test_cache_restores_a_close_from_persistent_storage() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.entries = {}

        def load(self, keys):
            return {key: self.entries[key] for key in keys if key in self.entries}

        def save(self, key, value, fetched_at):
            self.entries[key] = (value, fetched_at)

    store = FakeStore()
    first = MarketDataCache(store=store)
    first.set("CN", "sh600000", "quote", {"price": 10.0}, datetime(2026, 9, 11, 15, 1))

    restored = MarketDataCache(store=store)

    assert restored.get("CN", "sh600000", "quote", datetime(2026, 9, 11, 21, 0)) == {"price": 10.0}


def test_cache_loads_multiple_quotes_with_one_persistent_query() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.load_calls = 0

        def load(self, keys):
            self.load_calls += 1
            return {key: ({"price": 10.0}, datetime(2026, 9, 11, 15, 1)) for key in keys}

        def save(self, key, value, fetched_at):
            pass

    store = FakeStore()
    cache = MarketDataCache(store=store)

    result = cache.get_many([("CN", "sh600000"), ("CN", "sz000001")], "quote", datetime(2026, 9, 11, 21, 0))

    assert result == {("CN", "SH600000"): {"price": 10.0}, ("CN", "SZ000001"): {"price": 10.0}}
    assert store.load_calls == 1


def test_research_cache_expires_instead_of_freezing_forever() -> None:
    cache = MarketDataCache()
    cache.set("CN", "sh600000", "research_v2", {"price": 10}, datetime(2026, 9, 11, 15, 1))
    assert cache.get("CN", "sh600000", "research_v2", datetime(2026, 9, 12, 15, 1)) is None


def test_quote_from_previous_session_expires_after_close() -> None:
    cache = MarketDataCache()
    cache.set("CN", "sh600000", "quote", {"price": 10}, datetime(2026, 9, 10, 15, 1))
    assert cache.get("CN", "sh600000", "quote", datetime(2026, 9, 11, 21, 0)) is None


def test_quote_batch_uses_one_durable_write():
    class Store:
        writes = []
        def load(self, keys): return {}
        def save_many(self, entries): self.writes.append(entries)
    store = Store()
    cache = MarketDataCache(store=store)
    cache.set_many([("CN", "sh600000", {"price": 10}), ("CN", "sz000001", {"price": 20})], "quote")
    assert len(store.writes) == 1
    assert len(store.writes[0]) == 2
    assert cache.get("CN", "sh600000", "quote")["price"] == 10


def test_unavailable_durable_cache_backs_off_reads_and_writes():
    from investment.data.market_cache import SupabaseMarketCacheStore
    class BrokenClient:
        calls = 0
        def table(self, name):
            self.calls += 1
            raise RuntimeError("unavailable")
    store = object.__new__(SupabaseMarketCacheStore)
    store.client = BrokenClient()
    store._retry_after = 0
    assert store.load([("CN", "SH600000", "quote")]) == {}
    assert store.load([("CN", "SZ000001", "quote")]) == {}
    store.save(("CN", "SH600000", "quote"), {"price": 10}, datetime.now())
    assert store.client.calls == 1


def test_old_quote_unit_cache_is_not_reused():
    class LegacyStore:
        def load(self, keys):
            old_key = ("CN", "SH600519", "quote")
            return {old_key: ({"volume": 38331}, datetime(2026, 9, 11, 15, 1))} if old_key in keys else {}
        def save(self, *args):
            pass
    cache = MarketDataCache(store=LegacyStore())
    assert cache.get("CN", "sh600519", "quote", datetime(2026, 9, 11, 21, 0)) is None
