import asyncio
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

market_scanner_stub = ModuleType("investment.data.market_scanner")
market_scanner_stub.enrich_stock_history = lambda rows, limit=120: rows
market_scanner_stub.scan_cn_market = lambda: {"rows": [], "generated_at": None, "cached": False}
sys.modules.setdefault("investment.data.market_scanner", market_scanner_stub)

stock_picker_stub = ModuleType("investment.data.stock_picker")
stock_picker_stub.CANDIDATE_POOL = []
stock_picker_stub.PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.modules.setdefault("investment.data.stock_picker", stock_picker_stub)

from investment.api.routes import formula_ranking as module


def test_cn_formula_ranking_enriches_history_before_scoring():
    rows = [
        {
            "ticker": "sh600001",
            "name": "测试一",
            "market": "CN",
            "price": 10.0,
            "today_change_percent": 1.0,
            "turnover_rate": 3.0,
            "volume_ratio": 1.2,
            "pe_ratio": 20.0,
            "pb_ratio": 2.0,
            "market_cap": 10_000_000_000,
            "change_60d": 12.0,
        }
    ]
    def enrich(selected, limit):
        assert limit >= 1
        return [{**selected[0], "change_5d": 4.0, "change_20d": 9.0, "change_60d": 12.0}]

    with (
        patch.object(
            module,
            "scan_cn_market",
            return_value={"rows": rows, "generated_at": "2026-07-21T15:00:00+08:00", "cached": False},
        ),
        patch.object(module, "enrich_stock_history", side_effect=enrich),
    ):
        response = asyncio.run(module.formula_ranking(market="CN", limit=20, mode="balanced"))
    result = response["result"]

    assert result["history_enriched_count"] == 1
    assert result["items"][0]["change_5d"] == 4.0
    assert result["items"][0]["change_20d"] == 9.0
