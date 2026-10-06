"""Run shared-formula walk-forward validation and preserve data provenance."""
from __future__ import annotations
import argparse
import json
import hashlib
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from investment.data.formula_backtest import prepare, walk_forward, volume_reference
from tune_stock_picker import download, TICKERS
from investment.data.foreign_formula import foreign_bars
from investment.data.formula_instruments import catalog
from investment.data.formula_universe import select_sample, frozen_sample
from investment.data.formula_fundamentals import attach_ledger
from investment.data.formula_provenance import research_provenance
from investment.data.hk_yahoo_history import load_hk_archive, hk_archive_folder
from investment.data.formula_execution import validate_execution, lot_reference_coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--sample-size", type=int, default=12)
    parser.add_argument("--market", choices=["CN", "HK", "US"], default="CN")
    parser.add_argument("--universe", choices=["snapshot", "catalog"], default="snapshot")
    parser.add_argument("--sample-manifest", type=Path, help="Freeze requested symbols from an existing report; other experiment settings remain explicit")
    parser.add_argument("--output", type=Path, help="Save a separate report without overwriting the default report")
    parser.add_argument("--fundamentals", action="store_true", help="US SEC filing-date valuations; never present-day fundamentals")
    parser.add_argument("--history-source", choices=["default", "baostock", "yahoo-hk"], default="default")
    parser.add_argument("--historical-reference", action="store_true", help="CN vendor historical PE/PB reference; revision timing unverified")
    parser.add_argument("--volume-reference", action="store_true", help="Completed-day volume / prior five sessions; only stable known share scales, not live intraday volume ratio")
    parser.add_argument("--tune-volume-weight", action="store_true", help="Research-only training grid for completed-day volume weights; requires --volume-reference")
    parser.add_argument("--execution-config", type=Path, help="Frozen JSON capital, minimum fee and optional raw-price entry lot scenario; requires separate output")
    args = parser.parse_args()
    execution = None
    if args.execution_config:
        if not args.output:
            parser.error("--execution-config requires a separate --output research report")
        try:
            execution = validate_execution(json.loads(args.execution_config.read_text(encoding="utf-8")), {args.market})
        except (OSError, ValueError, TypeError) as exc:
            parser.error(f"Invalid execution config: {exc}")
    if args.tune_volume_weight and not args.volume_reference:
        parser.error("--tune-volume-weight requires --volume-reference and a separate output")
    if args.sample_manifest and (not args.output or args.output.resolve() == args.sample_manifest.resolve()):
        parser.error("--sample-manifest requires a separate --output report")
    if args.volume_reference and not args.output:
        parser.error("--volume-reference requires a separate --output research report")
    if args.fundamentals and args.market != "US":
        parser.error("SEC fundamentals currently support US only")
    if args.history_source == "baostock" and (args.market != "CN" or args.download):
        parser.error("Use download_cn_formula_history.py first; BaoStock source supports cached CN histories only")
    if args.history_source == "yahoo-hk" and (args.market != "HK" or args.download or not args.output):
        parser.error("yahoo-hk requires cached HK research archives and separate --output")
    if args.historical_reference and (args.market != "CN" or args.history_source != "baostock"):
        parser.error("historical-reference requires CN BaoStock source")
    if not 8 <= args.sample_size <= 200:
        parser.error("sample-size must be between 8 and 200")
    sampling = None
    wanted = TICKERS
    if args.sample_manifest:
        try:
            raw_manifest = args.sample_manifest.read_bytes()
            manifest = json.loads(raw_manifest)
            if manifest.get("universe_source", args.universe) != args.universe:
                raise ValueError("样本来源不匹配，请明确指定--universe")
            sampling = frozen_sample(manifest, args.market)
            sampling["manifest_sha256"] = hashlib.sha256(raw_manifest).hexdigest()
            sampling["manifest_path"] = str(args.sample_manifest.resolve())
            wanted = sampling["selected"]
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            parser.error(f"Invalid sample manifest: {exc}")
    elif args.universe == "catalog":
        rows = [{**row, "market": market, "ticker": ticker.lower() if market in ("CN", "HK") else ticker} for (market, ticker), row in catalog().items()]
        sampling = select_sample(rows, args.market, args.sample_size)
        wanted = sampling["selected"]
    elif args.sample_size != 12 or args.market != "CN":
        snapshot_name = "latest.json" if args.market == "CN" else f"hot-{args.market.lower()}.json"
        snapshot = json.loads((ROOT / "storage/market" / snapshot_name).read_text(encoding="utf-8"))
        rows = [{**row, "market": args.market, **({"instrument_type": "stock"} if args.market == "CN" else {})} for row in snapshot["rows"]]
        sampling = select_sample(rows, args.market, args.sample_size)
        wanted = sampling["selected"]
    series = {}; failures = []; source_exclusions = {}
    def fetch(ticker):
        if args.market == "CN":
            return download(ticker)
        bars = foreign_bars(ticker, args.market)
        path = ROOT / "storage/stock_picker/history" / f"{ticker}.json"
        path.write_text(json.dumps({"downloaded_at": datetime.now(timezone.utc).isoformat(), "source": "腾讯/Yahoo日K", "market": args.market, "bars": bars}, ensure_ascii=False), encoding="utf-8")
        return ticker, bars
    if args.download:
        with ThreadPoolExecutor(max_workers=6) as executor:
            jobs = {ticker: executor.submit(fetch, ticker) for ticker in wanted}
            for ticker, future in jobs.items():
                try:
                    name, bars = future.result(); series[name] = bars
                except Exception as exc:
                    failures.append({"ticker": ticker, "reason": str(exc)})
    else:
        for ticker in wanted:
            folder = ROOT / "storage/stock_picker/history"
            if args.history_source == "yahoo-hk":
                folder = hk_archive_folder(folder, args.universe)
            elif args.history_source == "baostock":
                folder = folder / args.history_source
            path = folder / f"{ticker}.json"
            if path.exists():
                try:
                    saved = load_hk_archive(folder, ticker) if args.history_source == "yahoo-hk" else json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError, KeyError, RuntimeError) as exc:
                    failures.append({"ticker": ticker, "reason": str(exc)})
                    continue
                if args.history_source in ("baostock", "yahoo-hk") and not saved.get("code_validated"):
                    failures.append({"ticker": ticker, "reason": "归档缺少逐行证券代码校验，需重取"})
                    continue
                exclusions = saved.get("excluded_by_reason", {})
                if exclusions.get("invalid_price") or exclusions.get("invalid_ohlc"):
                    failures.append({"ticker": ticker, "reason": "旧归档曾删除异常活跃交易日，整只隔离"})
                    continue
                source_exclusions[ticker] = exclusions
                series[ticker] = saved["bars"]
            else:
                failures.append({"ticker": ticker, "reason": "未下载历史数据"})
    quality_failures = []
    for ticker, bars in list(series.items()):
        try:
            if len(bars) < 61:
                raise ValueError("历史不足61条有效交易日K")
            prepare({ticker: bars})
        except ValueError as exc:
            quality_failures.append({"ticker": ticker, "reason": str(exc)})
            del series[ticker]
    data_fingerprint = hashlib.sha256(json.dumps(series, sort_keys=True).encode("utf-8")).hexdigest()
    if args.historical_reference:
        series = {ticker: [{**row, "reference_research_enabled": True} for row in bars] for ticker, bars in series.items()}
    volume_coverage = None
    if args.volume_reference:
        counts = {}
        for bars in series.values():
            for index in range(60, len(bars)):
                status = volume_reference(bars, index)["status"]
                counts[status] = counts.get(status, 0) + 1
            for row in bars:
                row["volume_reference_enabled"] = True
        volume_coverage = {"status": "available" if counts.get("ok", 0) else "not_available", "observations": sum(counts.values()), "available": counts.get("ok", 0), "status_counts": counts, "basis": "完成日成交量/此前5个报价交易日平均；固定口径研究，非盘中供应商量比"}
    if args.tune_volume_weight and volume_coverage["available"] == 0:
        parser.error("No verified completed-day volume observations; weight tuning is unavailable")
    fundamental_coverage = None
    if args.fundamentals:
        missing = []
        for ticker, bars in series.items():
            path = ROOT / "storage/stock_picker/fundamentals" / f"{ticker}-ledger.json"
            ledger = json.loads(path.read_text(encoding="utf-8"))["points"] if path.exists() else []
            if not ledger:
                missing.append(ticker)
            series[ticker] = attach_ledger(bars, ledger)
        observations = sum(max(0, len(bars) - 60) for bars in series.values())
        fundamental_coverage = {"observations": observations, "pe_observations": sum("pe_ratio" in row for bars in series.values() for row in bars[60:]), "pb_observations": sum("pb_ratio" in row for bars in series.values() for row in bars[60:]), "cap_observations": sum("market_cap" in row for bars in series.values() for row in bars[60:]), "missing_ledgers": missing, "basis": "USD未复权股价×已披露股本；TTM利润以年报+当年YTD-上年可比YTD重建，PE/PB为估算", "availability": "提交日次日起可用；拆股/调整跳变后等待新股本期间；最长400天"}
    source_root = Path(__file__).resolve().parents[1]
    sources = ["scripts/backtest_formula.py", "data/formula_backtest.py", "data/formula_scoring.py", "data/formula_risk.py", "data/formula_fundamentals.py", "data/formula_provenance.py"]
    sources.append("data/formula_execution.py")
    if args.history_source == "yahoo-hk":
        sources.append("data/hk_yahoo_history.py")
    provenance = research_provenance(series, {"market": args.market, "history_source": args.history_source, "fundamentals": args.fundamentals, "historical_reference": args.historical_reference, "volume_reference": args.volume_reference, "tune_volume_weight": args.tune_volume_weight, **({"execution": execution} if execution else {})}, {name: source_root / name for name in sources})
    try:
        lot_coverage = lot_reference_coverage(series, execution)
        if lot_coverage and lot_coverage["available"] == 0:
            raise ValueError("冻结样本没有已披露且生效的每手参考记录；未计算收益，不回退到小数股")
        report = walk_forward(series, include_fundamentals=args.fundamentals or args.historical_reference, tune_volume_weight=args.tune_volume_weight, **({"execution": execution} if execution else {}))
    except ValueError as exc:
        report = {"status": "insufficient_data", "applied": False, "message": str(exc)}
    report.update({"market": args.market, "generated_at": datetime.now(timezone.utc).isoformat(), "source": "腾讯前复权日K" if args.market == "CN" else "腾讯/Yahoo日K", "universe_source": args.universe, "sampling": sampling, "selection_method": ("当前证券目录；" if args.universe == "catalog" else "当前行情快照；") + sampling["method"] if sampling else "预先固定的12只股票", "requested_count": len(wanted), "available_count": len(series), "download_failures": failures, "quality_failures": quality_failures})
    filename = "formula-backtest.json" if args.market == "CN" else f"formula-backtest-{args.market.lower()}.json"
    if args.universe == "catalog":
        filename = filename.replace(".json", "-catalog.json")
    if args.history_source == "baostock":
        filename = filename.replace(".json", "-baostock.json")
        report["source"] = "BaoStock前复权日K"
        report["history_exclusions"] = source_exclusions
    if args.history_source == "yahoo-hk":
        filename = filename.replace(".json", "-yahoo-hk.json")
        report["source"] = "Yahoo港股同响应原价与复权价研究归档"
        report.setdefault("limitations", []).append("独立Yahoo来源实验；与腾讯归档差异不能全部归因于量能；复权仍非时点公司行动账本")
    if args.historical_reference:
        filename = filename.replace(".json", "-reference.json")
        report["fundamental_mode"] = "cn-reference"
        report["formula_scope"] = "共享评分引擎；历史价格＋日K接口PE/PB/换手率参考，财务修订时间未验证"
        report.setdefault("limitations", []).append("历史接口估值可能使用修订后的财务数值；这是参考研究，不能宣称严格PIT或用于自动应用参数")
    if args.fundamentals:
        filename = filename.replace(".json", "-pit.json")
        report["fundamental_coverage"] = fundamental_coverage
        report["formula_scope"] = "共享实时评分引擎；历史价格因子＋SEC披露日期估值/市值估算；缺失指标贡献0，不填入当前值"
        report["fundamental_mode"] = "sec-pit"
        report.setdefault("limitations", []).extend(["SEC us-gaap USD 10-K/10-Q口径，外国公司/IFRS等缺失；股本估计市值、净利润估计PE不等于稀释每股盈利口径", "提交日次日可用的保守假设；当时股本并非精确实时总股本", "使用未复权价估值，复权OHLC用于价格因子；历史复权仍缺时点公司行动记录", "量比、换手率等仍未完成历史验证；没有完成全因子验证"])
    if args.sample_manifest:
        report["selection_method"] = sampling["method"]
    path = args.output.resolve() if args.output else ROOT / "storage/stock_picker" / filename
    report["data_fingerprint"] = data_fingerprint
    report.update(provenance)
    if execution and "lot_ledger" in execution:
        report["execution_lot_coverage"] = lot_coverage
        report["execution_scenario"] = execution
        report.setdefault("limitations", []).append("每手记录仅来自人工核验的公告短区间参考，非完整历史规则；未覆盖日期拒绝买入，不使用当前每手值回填")
    if args.volume_reference:
        report["volume_reference_coverage"] = volume_coverage
        report["formula_scope"] = report.get("formula_scope", "共享评分引擎研究") + "；加入完成日5日成交量倍数研究（非盘中量比）"
        report.setdefault("limitations", []).append("量能参考要求6日正成交量、已知且稳定share_scale、行情来源一致、无超过7日的报价间隔；仍未验证历史公司行动及真实盘中量比")
    if args.market in ("HK", "US"):
        provenance = {}
        for bars in series.values():
            for row in bars:
                key = f"{row.get('history_source', 'legacy-unverified')}:{row.get('price_basis', 'legacy-unverified')}"
                provenance[key] = provenance.get(key, 0) + 1
        report["history_price_basis"] = provenance
        report["history_date_ranges"] = {ticker: {"first": bars[0]["date"], "last": bars[-1]["date"], "bars": len(bars)} for ticker, bars in series.items() if bars}
        report.setdefault("limitations", []).append("逐日行情来源/复权口径见history_price_basis；原价序列的除权除息可能产生非交易收益跳变，未完成公司行动调整")
        report["limitations"].append("各证券行情起止日见history_date_ranges；停牌或历史提前终止时无法成交，已有持仓沿用最后报价，可能低估流动性与退市损失")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("out_of_sample", "folds", "sampling")}, ensure_ascii=False))
    for key, result in report.get("out_of_sample", {}).items():
        print(key, {name: value for name, value in result.items() if name != "equity_curve"})


if __name__ == "__main__":
    main()
