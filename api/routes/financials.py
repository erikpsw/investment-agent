"""
Financial Data API Routes
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException

from investment.data import StockFetcher
from investment.api.schemas import FinancialMetrics

router = APIRouter()
fetcher = StockFetcher()


def _get_metric(metrics: Dict[str, Any], *keys: str) -> Optional[float]:
    """尝试多个可能的字段名获取指标值
    
    AKShare 返回的字段名可能带有 (%) 后缀，如 "净资产收益率(%)"
    """
    for key in keys:
        # 直接匹配
        if key in metrics and metrics[key] is not None:
            val = metrics[key]
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                try:
                    return float(val.replace("%", "").replace(",", ""))
                except ValueError:
                    continue
        
        # 尝试带括号的变体
        for suffix in ["(%)", "(倍)", "(次)"]:
            key_with_suffix = f"{key}{suffix}"
            if key_with_suffix in metrics and metrics[key_with_suffix] is not None:
                val = metrics[key_with_suffix]
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    try:
                        return float(val.replace("%", "").replace(",", ""))
                    except ValueError:
                        continue
    
    return None


@router.get("/financials/{ticker}", response_model=FinancialMetrics)
async def get_financials(ticker: str):
    """Get key financial metrics for a stock"""
    try:
        metrics = fetcher.get_key_metrics(ticker)
        
        if "error" in metrics:
            raise HTTPException(status_code=404, detail=metrics["error"])
        
        pe_ratio = _get_metric(metrics, "pe_ratio", "市盈率", "市盈率(动态)", "市盈率TTM")
        quote = fetcher.get_quote(ticker)
        if pe_ratio is None and quote.get("pe_ratio"):
            pe_ratio = quote.get("pe_ratio")
        
        return FinancialMetrics(
            ticker=ticker,
            name=metrics.get("name") or quote.get("name"),
            pe_ratio=pe_ratio,
            pb_ratio=_get_metric(metrics, "pb_ratio", "市净率"),
            roe=_get_metric(metrics, "roe", "净资产收益率", "加权净资产收益率", "摊薄净资产收益率"),
            roa=_get_metric(metrics, "roa", "总资产收益率", "总资产报酬率"),
            gross_margin=_get_metric(metrics, "gross_margin", "毛利率", "销售毛利率"),
            profit_margin=_get_metric(metrics, "profit_margin", "净利率", "销售净利率"),
            debt_ratio=_get_metric(metrics, "debt_ratio", "资产负债率"),
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
