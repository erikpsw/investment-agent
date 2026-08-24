from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from investment.api.routes import search as search_route
from investment.api.routes.search import search_stocks
from investment.data.portfolio import PortfolioService
from investment.data.portfolio_store import InMemoryPortfolioStore
from investment.data.stock_search import StockSearch, _instrument_type, search_etf_catalog


class EtfDiscoveryTests(unittest.TestCase):
    def test_exact_live_us_etf_outranks_stale_fuzzy_catalog_results(self) -> None:
        class StaleFetcher:
            def search(self, query, market="all", limit=10):
                return [
                    {
                        "code": "INTC" if query == "INT" else "FIRE",
                        "name": "stale fuzzy match",
                        "market": "US",
                        "display": "stale fuzzy match",
                        "exchange": "NASDAQ",
                        "instrument_type": "stock",
                    }
                ]

        live = {
            "IRE": {
                "code": "IRE",
                "name": "Defiance Daily Target 2X Long IREN ETF",
                "market": "US",
                "display": "Defiance Daily Target 2X Long IREN ETF (IRE)",
                "exchange": "NYSEArca",
                "instrument_type": "etf",
            },
            "INT": {
                "code": "INT",
                "name": "Corgi INTC 2x Daily ETF",
                "market": "US",
                "display": "Corgi INTC 2x Daily ETF (INT)",
                "exchange": "Cboe US",
                "instrument_type": "etf",
            },
        }

        with (
            patch.object(search_route, "fetcher", StaleFetcher()),
            patch.object(search_route, "_supabase_searcher", None),
            patch.object(search_route, "_search_yfinance", side_effect=lambda query, limit=5: [live[query]]),
        ):
            for ticker in ("IRE", "INT"):
                response = asyncio.run(search_stocks(q=ticker, market="US", limit=5))
                self.assertEqual(response.results[0].code, ticker)
                self.assertEqual(response.results[0].instrument_type, "etf")

    def test_live_us_symbol_probe_preserves_etf_type_and_exchange(self) -> None:
        class FakeSearch:
            quotes = [{
                "symbol": "IRE",
                "shortname": "Defiance Daily Target 2X Long I",
                "longname": "Defiance Daily Target 2X Long IREN ETF",
                "quoteType": "EQUITY",
                "exchDisp": "NYSEArca",
            }]

        with (
            patch("yfinance.Search", return_value=FakeSearch()),
            patch("yfinance.Ticker", side_effect=AssertionError("slow info lookup must not run")),
        ):
            result = search_route._search_yfinance("IRE", limit=5)

        self.assertEqual(result[0]["code"], "IRE")
        self.assertEqual(result[0]["instrument_type"], "etf")
        self.assertEqual(result[0]["exchange"], "NYSEArca")

    def test_cn_etf_catalog_is_searchable_by_code_and_name(self) -> None:
        searcher = StockSearch()

        by_code = searcher.search("510300", market="cn", limit=5)
        by_name = searcher.search("沪深300ETF华泰柏瑞", market="cn", limit=5)

        self.assertTrue(any(item["code"] == "sh510300" for item in by_code))
        self.assertTrue(any(item["code"] == "sh510300" for item in by_name))
        self.assertEqual(by_code[0]["instrument_type"], "etf")

        lightweight = search_etf_catalog("510300", market="all", limit=5)
        self.assertEqual(lightweight[0]["code"], "sh510300")

    def test_instrument_name_can_identify_us_etf(self) -> None:
        self.assertEqual(
            _instrument_type("QQQ", listed_type="stock", name="Invesco QQQ ETF"),
            "etf",
        )

    def test_search_api_prioritizes_bundled_etf_catalog(self) -> None:
        response = asyncio.run(
            search_stocks(q="510300", market="all", limit=8)
        )

        self.assertEqual(response.results[0].code, "sh510300")
        self.assertEqual(response.results[0].instrument_type, "etf")

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
