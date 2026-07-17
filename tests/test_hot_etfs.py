from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from investment.data.etf_scanner import load_hot_etf_snapshot, rank_hot_etf_sectors


def etf(
    ticker: str,
    name: str,
    amount: float,
    change: float,
    turnover: float | None = None,
    volume_ratio: float | None = None,
    change_5d: float | None = None,
):
    return {
        "ticker": ticker,
        "name": name,
        "market": "CN",
        "price": 1.2,
        "amount": amount,
        "today_change_percent": change,
        "turnover_rate": turnover,
        "volume_ratio": volume_ratio,
        "change_5d": change_5d,
    }


class HotEtfSectorTests(unittest.TestCase):
    def test_filters_non_sector_products_and_selects_most_liquid_representative(self) -> None:
        rows = [
            etf("sh512480", "半导体ETF", 1000, 2, 4, 1.5, 5),
            etf("sh588200", "芯片ETF", 2000, 1, 3, 1.2, 4),
            etf("sz159819", "人工智能ETF", 1500, 3, 5, 2, 6),
            etf("sh511010", "国债ETF", 9999, 1),
            etf("sh518880", "黄金ETF", 9999, 1),
            etf("sz159941", "纳指ETF QDII", 9999, 1),
            etf("sh510300", "沪深300ETF", 9999, 1),
        ]

        ranked = rank_hot_etf_sectors(rows, limit=10)

        self.assertEqual({item["theme"] for item in ranked}, {"半导体", "人工智能"})
        semiconductor = next(item for item in ranked if item["theme"] == "半导体")
        self.assertEqual(semiconductor["ticker"], "sh588200")
        self.assertEqual(semiconductor["name"], "芯片ETF")

    def test_missing_five_day_momentum_redistributes_available_weights(self) -> None:
        ranked = rank_hot_etf_sectors(
            [
                etf("sh512480", "半导体ETF", 1000, 2, 4, 1.5, None),
                etf("sz159819", "人工智能ETF", 900, 1, 3, 1.2, None),
            ],
            limit=10,
        )

        self.assertEqual(
            set(ranked[0]["score_components"]),
            {"amount", "return", "activity"},
        )
        self.assertTrue(0 <= ranked[0]["heat_score"] <= 100)

    def test_loader_uses_stale_snapshot_when_provider_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hot-etfs.json"
            path.write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-15T07:15:00+00:00",
                        "source": "saved ETF snapshot",
                        "rows": [etf("sh512480", "半导体ETF", 1000, 2)],
                    }
                ),
                encoding="utf-8",
            )

            snapshot = load_hot_etf_snapshot(
                fetch_rows=lambda: (_ for _ in ()).throw(RuntimeError("provider down")),
                snapshot_path=path,
            )

        self.assertTrue(snapshot["stale"])
        self.assertEqual(snapshot["source"], "saved ETF snapshot")


if __name__ == "__main__":
    unittest.main()
