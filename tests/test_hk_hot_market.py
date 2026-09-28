import unittest
from unittest.mock import patch

from investment.data.hot_stocks import _hk_eastmoney_rows, _yahoo_active_rows, load_hot_stock_snapshot


class Response:
    def raise_for_status(self):
        pass

    def json(self):
        return {"finance": {"result": [{"quotes": [
            {"symbol": "AAPL", "regularMarketPrice": 100, "regularMarketVolume": 100},
            {"symbol": "0700.HK", "regularMarketPrice": 500, "regularMarketVolume": 100},
        ]}]}}


class HongKongMarketTests(unittest.TestCase):
    @patch("investment.data.hot_stocks.requests.get")
    def test_eastmoney_hk_rows_are_normalized(self, get):
        get.return_value.raise_for_status.return_value = None
        get.return_value.json.return_value = {"data": {"diff": [
            {"f12": "700", "f14": "腾讯", "f2": 500, "f6": 100000, "f3": 1.2},
            {"f12": "AAPL", "f14": "Apple", "f2": 100, "f6": 10000},
        ]}}
        rows = _hk_eastmoney_rows()
        self.assertEqual([row["ticker"] for row in rows], ["hk00700"])
        self.assertEqual(rows[0]["market"], "HK")

    @patch("investment.data.hot_stocks.requests.get", return_value=Response())
    def test_us_symbols_are_not_mislabeled_as_hk(self, _):
        rows = _yahoo_active_rows("HK")
        self.assertEqual([row["ticker"] for row in rows], ["hk00700"])

    def test_wrong_market_snapshot_is_rejected(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hot-hk.json"
            path.write_text(json.dumps({"market": "US", "rows": [{"ticker": "AAPL", "market": "US"}]}))
            with self.assertRaises(ValueError):
                load_hot_stock_snapshot("HK", lambda: [], path)
