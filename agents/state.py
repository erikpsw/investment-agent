from typing import TypedDict, Annotated, Any
from operator import add


class InvestmentState(TypedDict, total=False):
    """投资分析 Agent 状态定义"""
    
    query: str
    ticker: str
    market: str
    
    price_data: dict[str, Any]
    history_data: dict[str, Any]
    
    financials: dict[str, Any]
    key_metrics: dict[str, Any]
    
    technical_analysis: str
    
    sentiment_score: float
    sentiment_summary: str
    news: list[dict[str, Any]]
    
    report_search_results: list[dict[str, Any]]
    report_qa_answer: str
    
    risk_assessment: str
    risk_factors: list[str]
    
    recommendation: str
    confidence: float
    
    errors: Annotated[list[str], add]
    
    messages: Annotated[list[dict[str, Any]], add]


def create_initial_state(query: str, ticker: str = "") -> InvestmentState:
    """创建初始状态
    
    Args:
        query: 用户查询
        ticker: 股票代码（可选）
    """
    market = ""
    ticker_lower = ticker.lower() if ticker else ""
    
    if ticker_lower.startswith(("sh", "sz")) or ticker_lower.isdigit():
        market = "CN"
    elif ticker_lower.startswith("hk") or ticker.endswith(".HK"):
        market = "HK"
    elif ticker:
        market = "US"
    
    return InvestmentState(
        query=query,
        ticker=ticker,
        market=market,
        price_data={},
        history_data={},
        financials={},
        key_metrics={},
        technical_analysis="",
        sentiment_score=0.0,
        sentiment_summary="",
        news=[],
        report_search_results=[],
        report_qa_answer="",
        risk_assessment="",
        risk_factors=[],
        recommendation="",
        confidence=0.0,
        errors=[],
        messages=[],
    )
