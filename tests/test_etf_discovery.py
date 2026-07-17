from __future__ import annotations

import unittest

from investment.data.portfolio import PortfolioService
from investment.data.portfolio_store import InMemoryPortfolioStore
from investment.data.stock_search import StockSearch


class EtfDiscoveryTests(unittest.TestCase):
    def test_shanghai_and_shenzhen_etf_codes_resolve_with_instrument_type(self) -> None:
        searcher = StockSearch()

        shanghai = searcher.resolve("510300")
        shenzhen = searcher.resolve("159915")
        newer_prefix = searcher.resolve("516999")

        self.assertEqual(shanghai["code"], "sh510300")
        self.assertEqual(shanghai["instrument_type"], "etf")
        self.assertEqual(shenzhen["code"], "sz159915")
        self.assertEqual(shenzhen["instrument_type"], "etf")
        self.assertEqual(newer_prefix["code"], "sh516999")
        self.assertEqual(newer_prefix["instrument_type"], "etf")

    def test_etf_position_uses_existing_quote_and_cny_valuation_flow(self) -> None:
        class FakeFetcher:
            def get_quote(self, ticker):
                return {"ticker": ticker, "name": "沪深300ETF", "price": 4.2, "change_percent": 1.5}

        service = PortfolioService(
            store=InMemoryPortfolioStore(),
            fx_rate_provider=lambda: {"CNY": 1.0, "HKD": 0.9, "USD": 7.0},
        )
        service.fetcher = FakeFetcher()

        result = service.save_positions(
            "auth0|alice",
            [
                {
                    "ticker": "sh510300",
                    "name": "沪深300ETF",
                    "market": "CN",
                    "quantity": 1000,
                    "avg_cost": 4.0,
                }
            ],
        )

        position = result["positions"][0]
        self.assertEqual(position["current_price"], 4.2)
        self.assertEqual(position["market_value"], 4200)
        self.assertEqual(position["pnl"], 200)
        self.assertEqual(position["pnl_percent"], 5)


if __name__ == "__main__":
    unittest.main()
