"""Formula-based stock ranking for the Vercel lite deployment."""
from __future__ import annotations

import asyncio
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from investment.data.market_scanner import enrich_stock_history
from investment.data.cn_live_scanner import scan_cn_market
from investment.data.stock_picker import CANDIDATE_POOL, PROJECT_ROOT
from investment.data.formula_scoring import FormulaMode, VERSION, score_item, number as _num, describe
from investment.data.foreign_live_scanner import scan_foreign_market
from investment.data.foreign_live_history import enrich_foreign_history
from investment.data.formula_instruments import classify_instrument
from investment.data.detail_valuation import detail_valuation
from investment.api.report_bundle import read_research_bytes, bundle_folder
from investment.api.history_price_metadata import history_price_metadata


router = APIRouter()


@router.get("/formula-ranking/us-cover-research")
async def us_cover_research():
    from investment.api.us_cover_summary import read_summary
    try:
        return {"status": "ok", "result": await asyncio.to_thread(read_summary, PROJECT_ROOT)}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "美股补充研究暂不可用") from exc


@router.get("/formula-ranking/risk-budget-backtest")
async def risk_budget_backtest(market: str = Query("CN", pattern="^(CN|HK|US)$"), mode: FormulaMode = "balanced",
                               source_fingerprint: str = Query(..., pattern="^[a-f0-9]{64}$")):
    from investment.api.risk_budget_reports import read_summary
    try:
        result = await asyncio.to_thread(read_summary, PROJECT_ROOT, market, mode, source_fingerprint)
        return {"status": "ok", "result": result}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "风险预算实验暂不可用") from exc


@router.get("/formula-ranking/centered-risk-backtest")
async def centered_risk_backtest(market: str = Query("CN", pattern="^(CN|HK|US)$"), mode: FormulaMode = "balanced",
                                source_fingerprint: str = Query(..., pattern="^[a-f0-9]{64}$")):
    from investment.api.centered_risk_reports import read_summary
    try:
        result = await asyncio.to_thread(read_summary, PROJECT_ROOT, market, mode, source_fingerprint)
        return {"status": "ok", "result": result}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "扩展风控网格实验暂不可用") from exc


@router.get("/formula-ranking/reviewed-hk-backtest")
async def reviewed_hk_backtest(market: str = Query("HK", pattern="^HK$"), mode: FormulaMode = "balanced",
                               source_fingerprint: str = Query(..., pattern="^[a-f0-9]{64}$")):
    from investment.api.reviewed_hk_reports import read_summary
    try:
        result = await asyncio.to_thread(read_summary, PROJECT_ROOT, mode, source_fingerprint)
        return {"status": "ok", "result": result}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "港股财务因子对照暂不可用") from exc

FORMULA_DESCRIPTION = describe()


def _detail_identity(ticker: str) -> tuple[str, str]:
    ticker = ticker.strip()
    if re.fullmatch(r"(?i)(sh|sz|bj)\d{6}", ticker):
        return ticker.lower(), "CN"
    if re.fullmatch(r"\d{6}", ticker):
        prefix = "sh" if ticker.startswith("6") else "bj" if ticker.startswith(("4", "8", "9")) else "sz"
        return prefix + ticker, "CN"
    if re.fullmatch(r"(?i)(hk\d{4,5}|\d{4,5}(\.hk)?)", ticker):
        code = ticker.lower().removeprefix("hk").removesuffix(".hk")
        return "hk" + code.zfill(5), "HK"
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,14}", ticker):
        return ticker.upper(), "US"
    raise HTTPException(422, "请输入可识别的A股、港股或美股证券代码")


def _detail_quote(ticker: str) -> dict:
    from investment.api.routes.quotes import fetcher
    return fetcher.get_quote(ticker)


async def _detail_financials(ticker: str) -> dict:
    from investment.api.routes.financials import get_financials
    return (await get_financials(ticker)).model_dump()


@router.get("/formula-ranking/stock/{ticker}")
async def formula_stock_score(ticker: str, mode: FormulaMode = Query("balanced")):
    canonical, market = _detail_identity(ticker)
    classification = classify_instrument({"ticker": canonical, "market": market})
    if classification["instrument_type"] != "stock" or (market == "HK" and canonical[2:].startswith("8")):
        return {"status": "ok", "result": {"status": "not_supported", "message": "此证券不是已核验的普通股票，暂不提供股票公式评分", "classification": classification}}
    try:
        quote = await asyncio.wait_for(asyncio.to_thread(_detail_quote, canonical), timeout=20)
    except Exception as exc:
        raise HTTPException(503, "量化评分行情暂不可用，请稍后重试") from exc
    if not isinstance(quote, dict) or _num(quote.get("price")) is None or _num(quote["price"]) <= 0 or quote.get("error"):
        raise HTTPException(503, "缺少有效价格，暂不能计算量化评分")
    if quote.get("ticker") and _detail_identity(str(quote["ticker"])) != (canonical, market):
        raise HTTPException(503, "行情证券代码不匹配，暂不能计算量化评分")
    classification = classify_instrument({**quote, "ticker": canonical, "market": market})
    if classification["instrument_type"] != "stock":
        return {"status": "ok", "result": {"status": "not_supported", "message": "行情证券类型不适用普通股票评分", "classification": classification}}
    raw_stamp = quote.get("timestamp")
    stamp = None
    if isinstance(raw_stamp, str) and quote.get("timestamp_status") not in {"unverified_timezone", "unavailable"}:
        try:
            parsed = datetime.fromisoformat(raw_stamp.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                stamp = raw_stamp
        except ValueError:
            pass
    row = {key: quote.get(key) for key in ("name", "price", "pe_ratio", "pb_ratio", "market_cap", "turnover_rate", "volume_ratio")}
    row.update({"ticker": canonical, "market": market, "today_change_percent": quote.get("change_percent"), "source": quote.get("source"), "quote_as_of": stamp, **classification})
    enrich = enrich_stock_history if market == "CN" else enrich_foreign_history
    async def history():
        try:
            enriched = await asyncio.wait_for(asyncio.to_thread(enrich, [row], limit=1, as_of=row["quote_as_of"]), timeout=20)
            return enriched[0]
        except Exception:
            return {**row, "history_error": "历史日K暂不可用，趋势与保护价保持缺失"}
    async def financial_data():
        try:
            result = await asyncio.wait_for(_detail_financials(canonical), timeout=8)
            if not isinstance(result, dict) or result.get("error"):
                return None
            if result.get("ticker") and _detail_identity(str(result["ticker"])) != (canonical, market):
                return None
            return result
        except Exception:
            return None
    row, financials = await asyncio.gather(history(), financial_data())
    valuation = detail_valuation(quote, financials)
    row.update({key: valuation[key] for key in ("pe_ratio", "pb_ratio")})
    return {"status": "ok", "result": {"status": "ok", "mode": mode, "formula": describe(mode), "item": _rank_live_item(row, mode), "valuation": valuation, "financials_status": "available" if financials is not None else "unavailable", "source": quote.get("source"), "quote_as_of": stamp, "quote_time_status": quote.get("timestamp_status"), "provider_timestamp_raw": quote.get("provider_timestamp_raw"), "fetched_at": quote.get("fetched_at"), "scope": "单只股票共享公式评估；缺失因子不补分，不表示全市场排名"}}


@router.get("/formula-ranking/backtest")
async def formula_backtest_report(market: str = Query("CN", pattern="^(CN|HK|US)$"), universe: str = Query("snapshot", pattern="^(snapshot|catalog)$"), fundamentals: str = Query("price", pattern="^(price|sec-pit|cn-reference)$"), history_source: str = Query("default", pattern="^(default|baostock|yahoo-hk)$"), volume_reference: bool = Query(False), tune_volume_weight: bool = Query(False), execution_scenario: bool = Query(False), lot_reference: bool = Query(False), mode: FormulaMode = "balanced"):
    if lot_reference is True and (market != "HK" or execution_scenario is not True):
        raise HTTPException(422, "公告每手参考仅支持港股资金成交情景")
    if tune_volume_weight is True and volume_reference is not True:
        raise HTTPException(422, "量能权重调优需要同时开启完成日量能研究")
    filename = "formula-backtest.json" if market == "CN" else f"formula-backtest-{market.lower()}.json"
    if universe == "catalog":
        filename = filename.replace(".json", "-catalog.json")
    if history_source == "baostock":
        if market != "CN":
            raise HTTPException(422, "BaoStock历史行情验证当前仅支持A股")
        filename = filename.replace(".json", "-baostock.json")
    if history_source == "yahoo-hk":
        if market != "HK":
            raise HTTPException(422, "Yahoo港股配对归档当前仅支持港股")
        filename = filename.replace(".json", "-yahoo-hk.json")
    if fundamentals == "sec-pit":
        if market != "US":
            raise HTTPException(422, "SEC披露日期估值验证当前仅支持美股")
        filename = filename.replace(".json", "-pit.json")
    if fundamentals == "cn-reference":
        if market != "CN" or history_source != "baostock":
            raise HTTPException(422, "历史接口参考指标仅支持A股BaoStock归档")
        filename = filename.replace(".json", "-reference.json")
    if volume_reference is True:
        filename = filename.replace(".json", "-volume.json")
    if tune_volume_weight is True:
        filename = filename.replace(".json", "-tuned.json")
    if execution_scenario is True:
        filename = filename.replace(".json", "-execution.json")
    if lot_reference is True:
        filename = filename.replace(".json", "-lot-reference.json")
    if mode != "balanced":
        filename = filename.replace(".json", f"-mode-{mode}.json")
    try:
        content = await asyncio.to_thread(read_research_bytes, PROJECT_ROOT, filename)
        if content is None:
            return {"status": "ok", "result": {"status": "not_run", "applied": False, "message": "尚未归档该组合的资金成交情景报告" if execution_scenario is True else "尚未归档该组合的量能权重调优报告" if tune_volume_weight is True else "尚未运行共享公式滚动验证"}}
        result = json.loads(content)
        if result.get("formula_mode", "balanced") != mode:
            raise ValueError("Archived report mode mismatch")
        return {"status": "ok", "result": result}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "公式回测报告暂不可用") from exc


@router.get("/formula-ranking/joint-backtest")
async def formula_joint_backtest(market: str = Query("CN", pattern="^(CN|HK|US)$"), mode: FormulaMode = "balanced", source_fingerprint: str = Query(..., pattern="^[a-f0-9]{64}$")):
    prefix = {"CN": "cn-reference", "HK": "hk", "US": "us"}[market]
    filename = f"{prefix}-joint-{mode}.json"
    unavailable = {"status": "ok", "result": {"status": "not_run", "applied": False, "message": "当前样本、模式与因子组合尚未归档联合调优实验"}}
    try:
        def read_verified():
            report_bytes = read_research_bytes(PROJECT_ROOT, f"research/{filename}")
            if report_bytes is None:
                return None
            report = json.loads(report_bytes)
            source_bytes = read_research_bytes(PROJECT_ROOT, f"research/{prefix}-mode-{mode}.json")
            baseline = json.loads(source_bytes)
            if (report["market"] != market or report["formula_mode"] != mode or report["optimization_method"] != "joint-protected-grid-v1" or report["applied"] is not False
                    or hashlib.sha256(source_bytes).hexdigest() != report["source_report_sha256"]
                    or report["source_scoring_input_fingerprint"] != baseline["scoring_input_fingerprint"]
                    or report["data_fingerprint"] != baseline["data_fingerprint"]
                    or report["sequential_comparison"]["out_of_sample"] != baseline["out_of_sample"]["risk_tuned"]
                    or report["sequential_comparison"]["cost_stress"] != baseline["cost_stress"]):
                raise ValueError("Joint comparison identity mismatch")
            audit_name = "joint-research-audit.json" if mode == "balanced" else f"joint-research-audit-mode-{mode}.json"
            audit = json.loads(read_research_bytes(PROJECT_ROOT, audit_name))
            records = [row for row in audit["experiments"] if row["report"].split("/")[-1] == filename]
            if len(records) != 1 or records[0]["sha256"] != hashlib.sha256(report_bytes).hexdigest():
                raise ValueError("Joint report audit mismatch")
            return report
        result = await asyncio.to_thread(read_verified)
        if result is None or result["source_scoring_input_fingerprint"] != source_fingerprint:
            return unavailable
        return {"status": "ok", "result": result}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "联合调优报告或对照来源核验失败") from exc


@router.get("/formula-ranking")
async def formula_ranking(
    market: str = Query("CN", description="Market filter: CN, US, HK, all"),
    limit: int = Query(30, ge=1, le=100),
    mode: FormulaMode = Query("balanced", description="Risk mode"),
):
    if market.upper() == "ALL":
        responses = await asyncio.gather(*(formula_ranking(region, 100, mode) for region in ("CN", "HK", "US")))
        results = [response["result"] for response in responses]
        items = sorted([item for result in results for item in result["items"]], key=lambda item: (-item["formula_score"], item["ticker"]))
        return {"status": "ok", "result": {
            "market": "all", "mode": mode, "formula": describe(mode), "formula_version": VERSION,
            "items": items[:limit], "total": len(items), "generated_at": None,
            "scanned_count": sum(result.get("scanned_count", 0) for result in results),
            "candidate_count": sum(result.get("candidate_count", 0) for result in results),
            "history_enriched_count": sum(result.get("history_enriched_count", 0) for result in results),
            "cached": any(result.get("cached", False) for result in results),
            "snapshot_only": any(result.get("snapshot_only", False) for result in results),
            "market_sources": [{"market": result["market"], "generated_at": result.get("generated_at"), "source": result["source"], "cached": result.get("cached", False), "snapshot_only": result.get("snapshot_only", False)} for result in results],
            "source": "A股、港股、美股各自候选池合并",
            "scope": "各市场前100候选合并，数据日期分别显示；非全球全市场排名",
            "fallback": any(result.get("fallback", False) for result in results),
        }}
    if market.upper() in ("HK", "US"):
        try:
            region = market.upper()
            scan = await asyncio.to_thread(scan_foreign_market, region)
            rows = await asyncio.to_thread(enrich_foreign_history, scan["rows"], as_of=scan.get("generated_at"), limit=120)
            ranked = sorted([_rank_live_item(row, mode) for row in rows], key=lambda row: (-row["formula_score"], row["ticker"]))
            return {"status": "ok", "result": {"market": region, "mode": mode, "formula": describe(mode), "formula_version": VERSION, "items": ranked[:limit], "total": len(ranked), "candidate_count": len(rows), "scanned_count": len(scan["rows"]), "generated_at": scan.get("generated_at"), "source": scan.get("source") or f"{region}候选快照", "scope": "港股成交活跃候选池" if region == "HK" else "美股成交活跃候选池；非全部上市股票", "fallback": False, "cached": scan.get("cached", scan.get("stale", False)), "snapshot_only": scan.get("stale", False), "instrument_filter": scan.get("instrument_filter"), "history_enriched_count": sum(row.get("change_5d") is not None and row.get("change_20d") is not None and row.get("change_60d") is not None for row in ranked)}}
        except Exception:
            pass
    if market.upper() == "CN":
        try:
            scan = await asyncio.to_thread(scan_cn_market)
            enrichment_limit = 120
            enriched_rows = await asyncio.to_thread(enrich_stock_history, scan["rows"], limit=enrichment_limit, as_of=scan.get("generated_at"))
            ranked = [_rank_live_item(item, mode) for item in enriched_rows]
            ranked.sort(key=lambda item: item["formula_score"], reverse=True)
            history_enriched_count = sum(
                1
                for item in ranked
                if all(
                    isinstance(item.get(key), (int, float))
                    for key in ("change_5d", "change_20d", "change_60d")
                )
            )
            return {
                "status": "ok",
                "result": {
                    "generated_at": scan["generated_at"],
                    "market": "CN",
                    "mode": mode,
                    "formula": describe(mode),
                    "formula_version": VERSION,
                    "items": ranked[:limit],
                    "total": len(ranked),
                    "candidate_count": len(enriched_rows),
                    "scope": "沪深主板非ST股票；先按快照初筛120只候选，再补算历史并评分，非全池最终排名",
                    "scanned_count": len(scan["rows"]),
                    "history_enriched_count": history_enriched_count,
                    "cached": scan["cached"],
                    "snapshot_only": scan.get("stale", False),
                    "fallback": False,
                    "source": scan.get("source") or "沪深 A 股全市场快照",
                },
            }
        except Exception as exc:
            fallback_error = str(exc)
    else:
        fallback_error = None

    latest = _latest_result()
    rows = _collect_items(latest, market)
    ranked = [_rank_item(item, mode) for item in rows]
    ranked.sort(key=lambda item: item["formula_score"], reverse=True)
    return {
        "status": "ok",
        "result": {
            "generated_at": latest.get("generated_at") if isinstance(latest, dict) else None,
            "market": market,
            "mode": mode,
            "formula": describe(mode),
            "formula_version": VERSION,
            "items": ranked[:limit],
            "total": len(ranked),
            "scanned_count": len(rows),
            "cached": True,
            "fallback": True,
            "fallback_reason": fallback_error or "该市场暂无实时全池公式扫描，展示历史候选",
            "scope": "历史候选缓存，不代表实时市场排名",
            "candidate_count": len(rows),
            "source": "历史候选缓存 + 固定公式排序（全市场行情不可用时降级）",
        },
    }


@router.get("/formula-ranking/history")
async def formula_ranking_history(
    tickers: str = Query(..., min_length=1),
    mode: FormulaMode = Query("balanced"),
):
    wanted = [item.strip() for item in tickers.split(",") if item.strip()][:30]
    scan = await asyncio.to_thread(scan_cn_market)
    wanted_set = set(wanted)
    selected = [item for item in scan["rows"] if item.get("ticker") in wanted_set]
    enriched_rows = await asyncio.to_thread(enrich_stock_history, selected, limit=len(selected), as_of=scan.get("generated_at"))
    enriched = [
        item
        for item in enriched_rows
        if all(isinstance(item.get(key), (int, float)) for key in ("change_5d", "change_20d", "change_60d"))
    ]
    ranked = [_rank_live_item(item, mode) for item in enriched]
    ranked.sort(key=lambda item: item["formula_score"], reverse=True)
    return {
        "status": "ok",
        "result": {
            "items": ranked,
            "history_enriched_count": len(ranked),
            "requested_count": len(wanted),
        },
    }


def _rank_live_item(item: dict[str, Any], mode: FormulaMode) -> dict[str, Any]:
    return {**score_item(item, mode), "history_price_metadata": history_price_metadata(item)}


def _latest_result() -> dict[str, Any]:
    path = Path(PROJECT_ROOT) / "storage" / "stock_picker" / "results.jsonl"
    if not path.exists():
        return {}
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return {}
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            return value
    return {}


def _collect_items(latest: dict[str, Any], market: str) -> list[dict[str, Any]]:
    wanted = market.upper()
    by_ticker: dict[str, dict[str, Any]] = {}
    for group in ("recommendations", "watch_only", "avoid"):
        for item in latest.get(group, []) if isinstance(latest, dict) else []:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "")
            if not ticker:
                continue
            item_market = str(item.get("market") or "").upper()
            if wanted != "ALL" and item_market != wanted:
                continue
            row = dict(item)
            row["source_group"] = group
            by_ticker[ticker] = row

    if by_ticker:
        return list(by_ticker.values())

    for base in CANDIDATE_POOL:
        item_market = str(base.get("market") or "").upper()
        if wanted != "ALL" and item_market != wanted:
            continue
        by_ticker[str(base.get("ticker"))] = dict(base)
    return list(by_ticker.values())


def _rank_item(item: dict[str, Any], mode: FormulaMode) -> dict[str, Any]:
    return score_item(item, mode)


@router.get("/formula-ranking/holdout")
async def formula_holdout_report(market: str = Query("CN", pattern="^(CN|HK|US)$")):
    from investment.data.formula_holdout import digest,verify_engine
    from investment.data.frozen_formula_engine import verify_archive
    folder=Path(PROJECT_ROOT)/"storage"/"stock_picker"/"holdout"
    try:
        raw=await asyncio.to_thread(read_research_bytes,PROJECT_ROOT,f"holdout/protocol-{market.lower()}.json")
        if raw is None:
            return {"status":"ok","result":{"status":"not_run","applied":False,"message":"尚未冻结该市场的后续验证协议"}}
        protocol=json.loads(raw)
        if protocol["market"]!=market or digest({k:v for k,v in protocol.items() if k!="seal"})!=protocol["seal"]:
            raise ValueError("Protocol seal mismatch")
        if (folder/"engines"/protocol["seal"]).exists():
            await asyncio.to_thread(verify_archive,protocol,folder/"engines")
            engine_storage="archived"
        elif (bundle_folder(PROJECT_ROOT)/"holdout/engines"/protocol["seal"]).exists():
            await asyncio.to_thread(verify_archive,protocol,bundle_folder(PROJECT_ROOT)/"holdout/engines")
            engine_storage="archived"
        else:
            await asyncio.to_thread(verify_engine,protocol)
            engine_storage="live_hash_only"
        result={**protocol,"status":"awaiting_evaluation","engine_storage":engine_storage,"requested_count":len(protocol["requested_universe"]),"training_available_count":len(protocol["training_available_universe"])}
        evaluation=folder/f"evaluation-{market.lower()}.json"
        if evaluation.exists():
            data=json.loads(await asyncio.to_thread(evaluation.read_text,encoding="utf-8"))
            if data.get("protocol_seal")!=protocol["seal"]:raise ValueError("Evaluation protocol mismatch")
            result.update(data)
        result["applied"]=False
        return {"status":"ok","result":result}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise HTTPException(503,"冻结协议或评估报告校验失败，请重新核验实验；不会展示未匹配的收益。") from exc
