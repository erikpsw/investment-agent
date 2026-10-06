import asyncio


def test_execution_report_is_separate_and_missing_never_falls_back(tmp_path):
    import json
    from unittest.mock import patch
    from investment.api.routes import formula_ranking as module
    folder = tmp_path / "storage/stock_picker"
    folder.mkdir(parents=True)
    (folder / "formula-backtest-us-volume-tuned.json").write_text(json.dumps({"marker": "fractional"}))
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        result = asyncio.run(module.formula_backtest_report("US", "snapshot", "price", "default", True, True, True))["result"]
        assert result["status"] == "not_run"
        (folder / "formula-backtest-us-volume-tuned-execution.json").write_text(json.dumps({"marker": "execution"}))
        result = asyncio.run(module.formula_backtest_report("US", "snapshot", "price", "default", True, True, True))["result"]
        assert result["marker"] == "execution"


def test_lot_reference_requires_hk_execution_and_separate_report(tmp_path):
    import json
    from fastapi import HTTPException
    from investment.api.routes import formula_ranking as module
    folder = tmp_path / "storage/stock_picker"
    folder.mkdir(parents=True)
    (folder / "formula-backtest-hk-yahoo-hk-volume-tuned-execution.json").write_text(json.dumps({"marker": "fractional"}))
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        result = asyncio.run(module.formula_backtest_report("HK", "snapshot", "price", "yahoo-hk", True, True, True, True))["result"]
        assert result["status"] == "not_run"
        (folder / "formula-backtest-hk-yahoo-hk-volume-tuned-execution-lot-reference.json").write_text(json.dumps({"status": "insufficient_data"}))
        result = asyncio.run(module.formula_backtest_report("HK", "snapshot", "price", "yahoo-hk", True, True, True, True))["result"]
        assert result["status"] == "insufficient_data"
    for market, execution in [("CN", True), ("US", True), ("HK", False)]:
        try:
            asyncio.run(module.formula_backtest_report(market, "snapshot", "price", "default", False, False, execution, True))
        except HTTPException as error:
            assert error.status_code == 422
        else:
            raise AssertionError("Invalid lot combination accepted")
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

market_scanner_stub = ModuleType("investment.data.market_scanner")
market_scanner_stub.enrich_stock_history = lambda rows, limit=120, **kwargs: rows
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
    def enrich(selected, limit, as_of=None):
        assert limit >= 1
        assert as_of == "2026-07-21T15:00:00+08:00"
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


def test_catalog_backtest_report_is_separate_from_active_snapshot(tmp_path):
    import json
    folder = tmp_path / "storage" / "stock_picker"
    folder.mkdir(parents=True)
    (folder / "formula-backtest-us-catalog.json").write_text(json.dumps({"universe_source": "catalog", "available_count": 42}), encoding="utf-8")
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        result = asyncio.run(module.formula_backtest_report("US", "catalog"))["result"]
    assert result["available_count"] == 42
    assert result["universe_source"] == "catalog"


def test_sec_pit_report_is_not_substituted_with_price_only_report(tmp_path):
    import json
    folder = tmp_path / "storage" / "stock_picker"
    folder.mkdir(parents=True)
    (folder / "formula-backtest-us-catalog-pit.json").write_text(json.dumps({"fundamental_mode": "sec-pit", "available_count": 57}), encoding="utf-8")
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        result = asyncio.run(module.formula_backtest_report("US", "catalog", "sec-pit"))["result"]
    assert result["fundamental_mode"] == "sec-pit"


def test_cn_alternate_history_reference_has_its_own_report(tmp_path):
    import json
    folder = tmp_path / "storage" / "stock_picker"
    folder.mkdir(parents=True)
    (folder / "formula-backtest-catalog-baostock-reference.json").write_text(json.dumps({"fundamental_mode": "cn-reference", "source": "BaoStock"}), encoding="utf-8")
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        result = asyncio.run(module.formula_backtest_report("CN", "catalog", "cn-reference", "baostock"))["result"]
    assert result["fundamental_mode"] == "cn-reference"


def test_volume_report_is_separate_and_missing_combinations_do_not_fall_back(tmp_path):
    import json
    folder = tmp_path / "storage" / "stock_picker"
    folder.mkdir(parents=True)
    (folder / "formula-backtest-us-volume.json").write_text(json.dumps({"volume_reference_coverage": {"available": 5}}))
    (folder / "formula-backtest-us-catalog.json").write_text(json.dumps({"status": "research_only"}))
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        found = asyncio.run(module.formula_backtest_report("US", "snapshot", "price", "default", True))["result"]
        missing = asyncio.run(module.formula_backtest_report("US", "catalog", "price", "default", True))["result"]
    assert found["volume_reference_coverage"]["available"] == 5
    assert missing["status"] == "not_run"


def test_tuned_volume_report_is_independent_and_never_falls_back(tmp_path):
    import json
    folder = tmp_path / "storage/stock_picker"
    folder.mkdir(parents=True)
    (folder / "formula-backtest-us-pit-volume.json").write_text(json.dumps({"marker": "fixed"}))
    (folder / "formula-backtest-us-pit-volume-tuned.json").write_text(json.dumps({"marker": "tuned", "volume_weight_tuning": {"enabled": True}}))
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        found = asyncio.run(module.formula_backtest_report("US", "snapshot", "sec-pit", "default", True, True))["result"]
        fixed = asyncio.run(module.formula_backtest_report("US", "snapshot", "sec-pit", "default", True, False))["result"]
        missing = asyncio.run(module.formula_backtest_report("US", "catalog", "sec-pit", "default", True, True))["result"]
    assert found["marker"] == "tuned"
    assert fixed["marker"] == "fixed"
    assert missing["status"] == "not_run"
    assert "量能权重" in missing["message"]


def test_volume_weight_tuning_requires_volume_research():
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        asyncio.run(module.formula_backtest_report("US", "snapshot", "price", "default", False, True))
    assert exc.value.status_code == 422


def test_hk_yahoo_source_selects_independent_reports_and_rejects_other_markets(tmp_path):
    import json, pytest
    from fastapi import HTTPException
    folder = tmp_path / "storage/stock_picker"; folder.mkdir(parents=True)
    (folder / "formula-backtest-hk-yahoo-hk-volume-tuned.json").write_text(json.dumps({"marker": "yahoo-tuned"}))
    (folder / "formula-backtest-hk-volume.json").write_text(json.dumps({"marker": "old"}))
    with patch.object(module, "PROJECT_ROOT", tmp_path):
        found = asyncio.run(module.formula_backtest_report("HK", "snapshot", "price", "yahoo-hk", True, True))["result"]
        missing = asyncio.run(module.formula_backtest_report("HK", "catalog", "price", "yahoo-hk", True, False))["result"]
        assert found["marker"] == "yahoo-tuned"
        assert missing["status"] == "not_run"
        for market in ("CN", "US"):
            with pytest.raises(HTTPException) as exc:
                asyncio.run(module.formula_backtest_report(market, "snapshot", "price", "yahoo-hk", False, False))
            assert exc.value.status_code == 422
