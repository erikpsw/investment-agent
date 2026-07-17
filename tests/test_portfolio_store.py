from __future__ import annotations

import unittest

from investment.data.portfolio import PortfolioService
from investment.data.portfolio_store import InMemoryPortfolioStore


class PortfolioStoreTests(unittest.TestCase):
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
        self.assertEqual(by_ticker["CASH"]["market_value"], 7000)
        self.assertEqual(result["valuation_currency"], "CNY")

    def test_users_have_independent_portfolio_documents(self) -> None:
        store = InMemoryPortfolioStore()
        store.save(
            "auth0|alice",
            [{"ticker": "CASH", "market": "CASH", "quantity": 1000, "avg_cost": 1}],
        )
        store.save(
            "auth0|bob",
            [{"ticker": "CASH", "market": "CASH", "quantity": 250, "avg_cost": 1}],
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
                    "ticker": "CASH",
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
                    "ticker": "CASH",
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
