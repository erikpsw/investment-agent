"""
Financial Data API Routes
"""
import asyncio

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
import akshare as ak
import re

from investment.data import StockFetcher
from investment.api.schemas import FinancialMetrics
from investment.data.formula_scoring import number as _finite_number

router = APIRouter()
fetcher = StockFetcher()


def _parse_amount(val: str) -> Optional[float]:
    """解析金额字符串，统一转换为元"""
    if val is None or val == "False" or val == "" or val == "-":
        return None
    try:
        val_str = str(val).replace(",", "")
        multiplier = 1
        if "亿" in val_str:
            multiplier = 1e8
            val_str = val_str.replace("亿", "")
        elif "万" in val_str:
            multiplier = 1e4
            val_str = val_str.replace("万", "")
        return float(val_str) * multiplier
    except (ValueError, TypeError):
        return None


def _parse_percent(val: str) -> Optional[float]:
    """解析百分比字符串，返回小数形式"""
    if val is None or val == "False" or val == "" or val == "-":
        return None
    try:
        val_str = str(val).replace(",", "").replace("%", "")
        return float(val_str) / 100
    except (ValueError, TypeError):
        return None


def _get_metric(metrics: Dict[str, Any], *keys: str) -> Optional[float]:
    """尝试多个可能的字段名获取指标值
    
    AKShare 返回的字段名可能带有 (%) 后缀，如 "净资产收益率(%)"
    """
    for key in keys:
        # 直接匹配
        if key in metrics and metrics[key] is not None:
            val = metrics[key]
            if isinstance(val, (int, float)):
                result = _finite_number(val)
                if result is not None:
                    return result
            if isinstance(val, str):
                try:
                    result = _finite_number(val.replace("%", "").replace(",", ""))
                    if result is not None:
                        return result
                except ValueError:
                    continue
        
        # 尝试带括号的变体
        for suffix in ["(%)", "(倍)", "(次)"]:
            key_with_suffix = f"{key}{suffix}"
            if key_with_suffix in metrics and metrics[key_with_suffix] is not None:
                val = metrics[key_with_suffix]
                if isinstance(val, (int, float)):
                    result = _finite_number(val)
                    if result is not None:
                        return result
                if isinstance(val, str):
                    try:
                        result = _finite_number(val.replace("%", "").replace(",", ""))
                        if result is not None:
                            return result
                    except ValueError:
                        continue
    
    return None


def _ratio_metric(metrics: Dict[str, Any], standard_key: str, *percent_keys: str) -> Optional[float]:
    """Yahoo ratios are fractions; Chinese percentage indicators are percentage points."""
    if metrics.get(standard_key) is not None:
        value = _get_metric(metrics, standard_key)
        return value / 100 if value is not None and "%" in str(metrics[standard_key]) else value
    value = _get_metric(metrics, *percent_keys)
    return value / 100 if value is not None else None


@router.get("/financials/{ticker}", response_model=FinancialMetrics)
async def get_financials(ticker: str):
    """Get key financial metrics for a stock"""
    try:
        metrics = await asyncio.to_thread(fetcher.get_key_metrics, ticker)
        
        if "error" in metrics:
            raise HTTPException(status_code=404, detail=metrics["error"])
        
        metric_pe = _get_metric(metrics, "pe_ratio", "市盈率TTM", "市盈率(TTM)")
        pe_ratio = metric_pe
        quote = await asyncio.to_thread(fetcher.get_quote, ticker) if pe_ratio is None or not metrics.get("name") else {}
        if pe_ratio is None and metrics.get("pe_basis") != "TTM" and _finite_number(quote.get("pe_ratio")) is not None:
            pe_ratio = _finite_number(quote.get("pe_ratio"))
        
        pb_ratio = _get_metric(metrics, "pb_ratio", "市净率")
        return FinancialMetrics(
            ticker=ticker,
            name=metrics.get("name") or quote.get("name"),
            pe_ratio=pe_ratio,
            eps=_finite_number(metrics.get("eps")) if _finite_number(metrics.get("eps")) is not None else _finite_number(quote.get("eps")),
            source=metrics.get("source") or quote.get("source"),
            pe_source=(metrics.get("pe_source") or "AKShare") if metric_pe is not None or metrics.get("pe_basis") == "TTM" else quote.get("pe_source"),
            pe_basis=(metrics.get("pe_basis") or "TTM") if metric_pe is not None or metrics.get("pe_basis") == "TTM" else quote.get("pe_basis"),
            pb_ratio=pb_ratio,
            pb_source=(metrics.get("pb_source") or metrics.get("source") or "AKShare") if pb_ratio is not None else None,
            roe=_ratio_metric(metrics, "roe", "净资产收益率", "加权净资产收益率", "摊薄净资产收益率"),
            roa=_ratio_metric(metrics, "roa", "总资产收益率", "总资产报酬率"),
            gross_margin=_ratio_metric(metrics, "gross_margin", "毛利率", "销售毛利率"),
            profit_margin=_ratio_metric(metrics, "profit_margin", "净利率", "销售净利率"),
            debt_ratio=_ratio_metric(metrics, "debt_ratio", "资产负债率"),
            current_ratio=_get_metric(metrics, "current_ratio", "流动比率"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/financials/{ticker}/summary")
async def get_financial_summary(ticker: str):
    """Get full financial summary for a stock"""
    try:
        financials = fetcher.get_financials(ticker)
        return financials
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/financials/{ticker}/history")
async def get_financial_history(
    ticker: str,
    report_type: str = Query("annual", description="报告类型: annual(年报), q1, q2, q3, all"),
    limit: int = Query(10, ge=1, le=20, description="返回数量"),
):
    """获取财务历史数据，按报告类型筛选
    
    - annual: 只返回年报 (12-31)
    - q1: 只返回一季报 (03-31)  
    - q2: 只返回半年报 (06-30)
    - q3: 只返回三季报 (09-30)
    - all: 返回所有报告
    """
    code = ticker.lower().replace("sh", "").replace("sz", "")
    
    try:
        df = ak.stock_financial_abstract_ths(symbol=code)
        if df.empty:
            return {"ticker": ticker, "data": [], "report_type": report_type}
        
        # 按报告类型筛选
        report_filter = {
            "annual": "-12-31",
            "q1": "-03-31",
            "q2": "-06-30",
            "q3": "-09-30",
        }
        
        if report_type != "all" and report_type in report_filter:
            pattern = report_filter[report_type]
            df = df[df["报告期"].astype(str).str.contains(pattern)]
        
        # 取最近的数据
        df = df.tail(limit).iloc[::-1]  # 按时间倒序
        
        # 解析数据
        result = []
        for _, row in df.iterrows():
            result.append({
                "period": str(row.get("报告期", "")),
                "revenue": _parse_amount(row.get("营业总收入")),
                "revenue_yoy": _parse_percent(row.get("营业总收入同比增长率")),
                "net_profit": _parse_amount(row.get("净利润")),
                "net_profit_yoy": _parse_percent(row.get("净利润同比增长率")),
                "gross_margin": _parse_percent(row.get("销售毛利率")),
                "profit_margin": _parse_percent(row.get("销售净利率")),
                "roe": _parse_percent(row.get("净资产收益率")),
                "debt_ratio": _parse_percent(row.get("资产负债率")),
                "eps": _parse_amount(row.get("基本每股收益")),
                "bvps": _parse_amount(row.get("每股净资产")),
            })
        
        return {
            "ticker": ticker,
            "report_type": report_type,
            "data": result,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
