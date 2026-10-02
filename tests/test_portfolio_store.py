from __future__ import annotations

import unittest

from investment.data.portfolio import PortfolioService
from investment.data.portfolio_store import InMemoryPortfolioStore, SupabasePortfolioStore


class PortfolioStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        from unittest.mock import patch
        from investment.data.market_cache import MarketDataCache
        cache_patch = patch("investment.data.portfolio.get_market_data_cache", side_effect=MarketDataCache)
        cache_patch.start()
        self.addCleanup(cache_patch.stop)

    def test_fast_load_and_save_value_positions_without_research_calls(self) -> None:
        from unittest.mock import Mock
        from investment.data.market_cache import MarketDataCache
        store = InMemoryPortfolioStore()
        research = Mock()
        research.enrich.side_effect = AssertionError("Fast valuation must not fetch history or news")
        service = PortfolioService(store=store, research_service=research, market_cache=MarketDataCache(),
            fx_rate_provider=lambda: {"CNY": 1, "USD": 7, "HKD": 0.9})
        service.fetcher = Mock()
        service.fetcher.get_quote.return_value = {"price": 120, "name": "Apple"}
        saved = service.save_positions("alice", [{"ticker": "AAPL", "market": "US", "quantity": 2, "avg_cost": 100}])
        loaded = service.get_positions("alice", include_research=False)
        for result in (saved, loaded):
            position = result["positions"][0]
            self.assertEqual(position["market_value"], 1680)
            self.assertEqual(position["pnl"], 280)
            self.assertEqual(position["weight"], 100)
        research.enrich.assert_not_called()
        service.fetcher.get_quote.assert_called_once_with("AAPL")

    def test_supabase_load_retries_a_transient_gateway_timeout(self) -> None:
        class Query:
            attempts = 0

            def select(self, _fields): return self
            def eq(self, _field, _value): return self
            def limit(self, _count): return self
            def execute(self):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("HTTP 504 Gateway Timeout")
                return type("Response", (), {"data": []})()

        query = Query()
        client = type("Client", (), {"table": lambda self, _table: query})()
        store = SupabasePortfolioStore("https://example.supabase.co", "service-key", client)

        document = store.load("auth0|alice")

        self.assertEqual(query.attempts, 2)
        self.assertEqual(document.positions, [])
    def test_buy_uses_weighted_average_cost_and_deducts_native_cash(self) -> None:
        store = InMemoryPortfolioStore()
        store.save(
            "auth0|alice",
            [
                {"ticker": "AAPL", "name": "Apple", "market": "US", "currency": "USD", "quantity": 10, "avg_cost": 100},
                {"ticker": "CASH_USD", "market": "CASH", "currency": "USD", "quantity": 1000, "avg_cost": 1},
            ],
        )
        service = PortfolioService(store=store)

        result = service.apply_transaction(
            "auth0|alice",
            {
                "action": "buy",
                "instrument_id": "AAPL",
                "name": "Apple Inc.",
                "market": "US",
                "quantity": 5,
                "price": 160,
            },
        )

        positions = {item["ticker"]: item for item in result["positions"]}
        self.assertEqual(positions["AAPL"]["quantity"], 15)
        self.assertAlmostEqual(positions["AAPL"]["avg_cost"], 120)
        self.assertEqual(positions["CASH_USD"]["quantity"], 200)

    def test_partial_sell_adds_cash_and_recalculates_diluted_average_cost(self) -> None:
        store = InMemoryPortfolioStore()
        store.save(
            "auth0|alice",
            [
                {"ticker": "AAPL", "name": "Apple", "market": "US", "currency": "USD", "quantity": 10, "avg_cost": 100},
                {"ticker": "CASH_USD", "market": "CASH", "currency": "USD", "quantity": 50, "avg_cost": 1},
            ],
        )
        service = PortfolioService(store=store)

        result = service.apply_transaction(
            "auth0|alice",
            {"action": "sell", "instrument_id": "AAPL", "quantity": 4, "price": 150},
        )

        positions = {item["ticker"]: item for item in result["positions"]}
        self.assertEqual(positions["AAPL"]["quantity"], 6)
        self.assertAlmostEqual(positions["AAPL"]["avg_cost"], 400 / 6)
        self.assertEqual(positions["CASH_USD"]["quantity"], 650)

    def test_full_sell_removes_position_and_creates_matching_currency_cash(self) -> None:
        store = InMemoryPortfolioStore()
        store.save(
            "auth0|alice",
            [{"ticker": "hk00700", "name": "Tencent", "market": "HK", "currency": "HKD", "quantity": 20, "avg_cost": 300}],
        )
        service = PortfolioService(store=store)

        result = service.apply_transaction(
            "auth0|alice",
            {"action": "sell", "instrument_id": "hk00700", "quantity": 20, "price": 400},
        )

        positions = {item["ticker"]: item for item in result["positions"]}
        self.assertNotIn("hk00700", positions)
        self.assertEqual(positions["CASH_HKD"]["quantity"], 8000)

    def test_cash_can_be_set_or_adjusted_but_cannot_become_negative(self) -> None:
        store = InMemoryPortfolioStore()
        service = PortfolioService(store=store)

        service.apply_transaction(
            "auth0|alice",
            {"action": "set_cash", "currency": "CNY", "amount": 1000},
        )
        result = service.apply_transaction(
            "auth0|alice",
            {"action": "adjust_cash", "currency": "CNY", "amount": -250},
        )
        self.assertEqual(result["positions"][0]["ticker"], "CASH_CNY")
        self.assertEqual(result["positions"][0]["quantity"], 750)

        with self.assertRaisesRegex(ValueError, "cash balance cannot be negative"):
            service.apply_transaction(
                "auth0|alice",
                {"action": "adjust_cash", "currency": "CNY", "amount": -751},
            )

    def test_transaction_rejects_overselling_and_insufficient_cash(self) -> None:
        store = InMemoryPortfolioStore()
        store.save(
            "auth0|alice",
            [
                {"ticker": "AAPL", "market": "US", "currency": "USD", "quantity": 2, "avg_cost": 100},
                {"ticker": "CASH_USD", "market": "CASH", "currency": "USD", "quantity": 10, "avg_cost": 1},
            ],
        )
        service = PortfolioService(store=store)

        with self.assertRaisesRegex(ValueError, "sell quantity exceeds position"):
            service.apply_transaction(
                "auth0|alice",
                {"action": "sell", "instrument_id": "AAPL", "quantity": 3, "price": 150},
            )
        with self.assertRaisesRegex(ValueError, "insufficient USD cash"):
            service.apply_transaction(
                "auth0|alice",
                {"action": "buy", "instrument_id": "AAPL", "market": "US", "quantity": 1, "price": 11},
            )

    def test_portfolio_values_are_converted_to_cny(self) -> None:
        class FakeFetcher:
            prices = {"AAPL": 100, "hk00700": 60, "sh600000": 12}

            def get_quote(self, ticker):
                return {"price": self.prices[ticker], "name": ticker}

        store = InMemoryPortfolioStore()
        service = PortfolioService(
            store=store,
            fx_rate_provider=lambda: {"CNY": 1.0, "USD": 7.0, "HKD": 0.9},
        )
        service.fetcher = FakeFetcher()
        service.save_positions(
            "auth0|alice",
            [
                {"ticker": "AAPL", "market": "US", "quantity": 2, "avg_cost": 90},
                {"ticker": "hk00700", "market": "HK", "quantity": 10, "avg_cost": 50},
                {"ticker": "sh600000", "market": "CN", "quantity": 10, "avg_cost": 10},
                {"ticker": "CASH", "market": "CASH", "currency": "USD", "quantity": 1000, "avg_cost": 1},
            ],
        )

        result = service.get_positions("auth0|alice")
        by_ticker = {item["ticker"]: item for item in result["positions"]}

        self.assertEqual(by_ticker["AAPL"]["currency"], "USD")
        self.assertEqual(by_ticker["AAPL"]["market_value_native"], 200)
        self.assertEqual(by_ticker["AAPL"]["market_value"], 1400)
        self.assertEqual(by_ticker["AAPL"]["pnl"], 140)
        self.assertEqual(by_ticker["hk00700"]["market_value"], 540)
        self.assertEqual(by_ticker["sh600000"]["market_value"], 120)
        self.assertEqual(by_ticker["CASH_USD"]["market_value"], 7000)
        self.assertEqual(result["valuation_currency"], "CNY")

    def test_cash_currencies_are_unique_and_legacy_cash_becomes_cny(self) -> None:
        store = InMemoryPortfolioStore()
        service = PortfolioService(
            store=store,
            fx_rate_provider=lambda: {"CNY": 1.0, "USD": 7.0, "HKD": 0.9},
        )

        result = service.save_positions(
            "auth0|alice",
            [
                {"ticker": "CASH", "market": "CASH", "quantity": 100},
                {"ticker": "CASH_CNY", "market": "CASH", "currency": "CNY", "quantity": 999},
                {"ticker": "CASH_HKD", "market": "CASH", "currency": "HKD", "quantity": 200},
                {"ticker": "CASH_USD", "market": "CASH", "currency": "USD", "quantity": 300},
            ],
        )

        cash = {item["ticker"]: item for item in result["positions"]}
        self.assertEqual(set(cash), {"CASH_CNY", "CASH_HKD", "CASH_USD"})
        self.assertEqual(cash["CASH_CNY"]["quantity"], 100)
        self.assertEqual(cash["CASH_HKD"]["market_value"], 180)
        self.assertEqual(cash["CASH_USD"]["market_value"], 2100)

    def test_portfolio_research_history_is_opt_in(self) -> None:
        class FakeFetcher:
            def get_quote(self, ticker):
                return {"price": 12, "name": "浦发银行"}

        class FakeResearchService:
            def __init__(self) -> None:
                self.include_history = None

            def enrich(self, items, include_history=False):
                self.include_history = include_history
                return [
                    {
                        **item,
                        "research": {
                            "quote": {"price": 12, "day_change_percent": 1.0},
                            "history": [{"time": "2026-07-21", "close": 12}]
                            if include_history
                            else None,
                        },
                    }
                    for item in items
                ]

        research = FakeResearchService()
        service = PortfolioService(
            store=InMemoryPortfolioStore(),
            research_service=research,
        )
        service.fetcher = FakeFetcher()
        service.store.save(
            "auth0|alice",
            [{"ticker": "sh600000", "market": "CN", "quantity": 10, "avg_cost": 10}],
        )

        result = service.get_positions("auth0|alice", include_history=True)

        self.assertTrue(research.include_history)
        self.assertEqual(result["positions"][0]["research"]["history"][0]["close"], 12)

    def test_users_have_independent_portfolio_documents(self) -> None:
        store = InMemoryPortfolioStore()
        store.save(
            "auth0|alice",
            [{"ticker": "CASH_CNY", "market": "CASH", "quantity": 1000, "avg_cost": 1}],
        )
        store.save(
            "auth0|bob",
            [{"ticker": "CASH_CNY", "market": "CASH", "quantity": 250, "avg_cost": 1}],
        )

        alice = store.load("auth0|alice")
        bob = store.load("auth0|bob")

        self.assertEqual(alice.positions[0]["quantity"], 1000)
        self.assertEqual(bob.positions[0]["quantity"], 250)

    def test_portfolio_service_reads_and_analyzes_only_requested_user(self) -> None:
        store = InMemoryPortfolioStore()
        service = PortfolioService(store=store)
        service.save_positions(
            "auth0|alice",
            [
                {
                    "ticker": "CASH_CNY",
                    "name": "现金",
                    "market": "CASH",
                    "quantity": 1000,
                    "avg_cost": 1,
                    "notes": "reserve",
                }
            ],
        )
        service.save_positions(
            "auth0|bob",
            [
                {
                    "ticker": "CASH_CNY",
                    "name": "现金",
                    "market": "CASH",
                    "quantity": 250,
                    "avg_cost": 1,
                    "notes": "",
                }
            ],
        )

        alice = service.get_positions("auth0|alice")
        bob_analysis = service.analyze("auth0|bob")

        self.assertEqual(alice["positions"][0]["market_value"], 1000)
        self.assertEqual(alice["storage"], "memory")
        self.assertEqual(bob_analysis["total_market_value"], 250)


if __name__ == "__main__":
    unittest.main()
