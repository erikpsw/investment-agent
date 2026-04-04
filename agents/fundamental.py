from typing import Any
from .state import InvestmentState
from .llm import get_llm_client
from ..data import StockFetcher


fetcher = StockFetcher()


def analyze_fundamentals(state: InvestmentState) -> dict[str, Any]:
    """基本面分析节点
    
    分析内容：
    - 财务指标（ROE、利润率、资产周转率等）
    - 盈利能力
    - 成长性
    - 估值水平
    """
    ticker = state.get("ticker", "")
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    try:
        financials = fetcher.get_financials(ticker)
        key_metrics = fetcher.get_key_metrics(ticker)
        
        if "error" in key_metrics:
            return {
                "financials": {},
                "key_metrics": {},
                "errors": [f"获取财务数据失败: {key_metrics['error']}"],
            }
        
        llm = get_llm_client()
        analysis = llm.analyze(
            data={
                "ticker": ticker,
                "key_metrics": key_metrics,
            },
            task="对该股票进行基本面分析，评估其盈利能力、成长性、财务健康度和估值水平",
            format_hint="""请按以下格式输出：
## 盈利能力
...

## 成长性
...

## 财务健康度
...

## 估值水平
...

## 综合评价
..."""
        )
        
        return {
            "financials": {
                k: v.to_dict() if hasattr(v, "to_dict") else str(v)
                for k, v in financials.items()
            },
            "key_metrics": key_metrics,
            "messages": [{
                "role": "fundamental_agent",
                "content": analysis,
            }],
        }
        
    except Exception as e:
        return {"errors": [f"基本面分析失败: {str(e)}"]}


def get_financial_summary(state: InvestmentState) -> dict[str, Any]:
    """获取财务摘要（轻量版，不调用 LLM）"""
    ticker = state.get("ticker", "")
    if not ticker:
        return {"errors": ["缺少股票代码"]}
    
    try:
        key_metrics = fetcher.get_key_metrics(ticker)
        
        if "error" in key_metrics:
            return {"errors": [f"获取财务数据失败: {key_metrics['error']}"]}
        
        summary = {
            "ticker": ticker,
            "profitability": {
                "roe": key_metrics.get("roe"),
                "roa": key_metrics.get("roa"),
                "profit_margin": key_metrics.get("profit_margin"),
                "gross_margin": key_metrics.get("gross_margin"),
            },
            "valuation": {
                "pe_ratio": key_metrics.get("pe_ratio"),
                "pb_ratio": key_metrics.get("pb_ratio"),
            },
            "leverage": {
                "debt_to_equity": key_metrics.get("debt_to_equity"),
                "current_ratio": key_metrics.get("current_ratio"),
            },
        }
        
        return {
            "key_metrics": key_metrics,
            "messages": [{
                "role": "fundamental_agent",
                "content": f"财务摘要: {summary}",
            }],
        }
        
    except Exception as e:
        return {"errors": [f"获取财务摘要失败: {str(e)}"]}
