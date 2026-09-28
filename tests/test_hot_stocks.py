from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from investment.data.hot_stocks import load_hot_stock_snapshot, rank_hot_stocks


def row(
    ticker: str,
    amount: float,
    change: float,
    turnover: float | None = None,
    volume_ratio: float | None = None,
    name: str | None = None,
):
    return {
        "ticker": ticker,
        "name": name or ticker,
        "market": "CN",
        "price": 10.0,
        "amount": amount,
        "today_change_percent": change,
        "turnover_rate": turnover,
        "volume_ratio": volume_ratio,
    }


class HotStockRankingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            row(f"sh6000{index:02d}", 1000 - index * 70, index - 3, 1 + index, 1 + index / 10)
            for index in range(10)
        ]

    def test_composite_ranking_filters_invalid_names_and_low_liquidity_decile(self) -> None:
        candidates = self.rows + [
            row("sh600100", 999999, 10, 20, 8, name="ST Risk"),
            {**row("sh600101", 999999, 10), "price": 0},
        ]

        ranked = rank_hot_stocks(candidates, mode="hot", limit=20)

        tickers = [item["ticker"] for item in ranked]
        self.assertNotIn("sh600100", tickers)
        self.assertNotIn("sh600101", tickers)
        self.assertNotIn("sh600009", tickers)
        self.assertEqual(len(ranked), 9)
        self.assertTrue(all(0 <= item["heat_score"] <= 100 for item in ranked))
        self.assertIn("score_components", ranked[0])

    def test_amount_and_gainers_modes_use_the_requested_primary_factor(self) -> None:
        amount_ranked = rank_hot_stocks(self.rows, mode="amount", limit=3)
        gainers_ranked = rank_hot_stocks(self.rows, mode="gainers", limit=3)

        self.assertEqual([item["amount"] for item in amount_ranked], [1000, 930, 860])
        self.assertEqual(
            [item["today_change_percent"] for item in gainers_ranked],
            [5, 4, 3],
        )

    def test_missing_optional_factors_redistribute_weight(self) -> None:
        candidates = [
            row("A", 100, 3, None, None),
            row("B", 90, 1, None, None),
        ]

        ranked = rank_hot_stocks(candidates, mode="hot", limit=2)

        self.assertEqual(ranked[0]["ticker"], "A")
        self.assertEqual(
            set(ranked[0]["score_components"]),
            {"amount", "movement"},
        )

    def test_snapshot_loader_falls_back_to_last_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hot-us.json"
            path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-15T20:00:00+00:00",
                        "source": "saved",
                        "market": "US",
                        "rows": [{**row("AAPL", 100, 2), "market": "US"}],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = load_hot_stock_snapshot(
                "US",
                fetch_rows=lambda: (_ for _ in ()).throw(RuntimeError("provider down")),
                snapshot_path=path,
            )

        self.assertTrue(snapshot["stale"])
        self.assertEqual(snapshot["source"], "saved")
        self.assertEqual(snapshot["rows"][0]["ticker"], "AAPL")


if __name__ == "__main__":
    unittest.main()
