"""财报 AI 分析 API"""
import asyncio
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import akshare as ak

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=2)


class FinancialHighlight(BaseModel):
    metric: str
    value: str
    change: Optional[str] = None
    assessment: str
    comment: Optional[str] = None


class RiskFactor(BaseModel):
    category: str
    description: str
    severity: str


class ReportAnalysisResponse(BaseModel):
    ticker: str
    report_period: str
    report_type: str
    analysis_date: str
    summary: str
    revenue: Optional[dict] = None
    profit: Optional[dict] = None
    cash_flow: Optional[dict] = None
    highlights: List[FinancialHighlight] = []
    risks: List[RiskFactor] = []
    outlook: Optional[str] = None
    recommendation: Optional[str] = None
    confidence: float = 0.5
    error: Optional[str] = None


class AnalyzeRequest(BaseModel):
    ticker: str
    report_period: Optional[str] = None
    report_type: str = "年报"


def _fetch_financial_data(ticker: str) -> dict:
    """获取财务数据"""
    code = ticker.replace("sh", "").replace("sz", "").replace("SH", "").replace("SZ", "")
    result = {}
    
    try:
        df = ak.stock_financial_abstract_ths(symbol=code)
        if df is not None and not df.empty:
            latest = df.iloc[-1].to_dict()
            previous = df.iloc[-2].to_dict() if len(df) > 1 else {}
            result["latest"] = latest
            result["previous"] = previous
            result["periods"] = df["报告期"].tolist()[-8:]
    except Exception as e:
        result["error"] = str(e)
    
    try:
        info = ak.stock_individual_info_em(symbol=code)
        if info is not None and not info.empty:
            info_dict = {}
            for _, row in info.iterrows():
                info_dict[row["item"]] = row["value"]
            result["company_info"] = info_dict
    except Exception:
        pass
    
    return result


def _run_analysis(ticker: str, report_period: str, report_type: str) -> dict:
    """运行分析"""
    from investment.agents.tools.report_analyzer import (
        analyze_financial_report,
        load_cached_analysis,
    )
    
    cached = load_cached_analysis(ticker, report_period)
    if cached and "error" not in cached:
        return cached
    
    financial_data = _fetch_financial_data(ticker)
    
    stock_name = ""
    if "company_info" in financial_data:
        stock_name = financial_data["company_info"].get("股票简称", "")
    
    result = analyze_financial_report(
        ticker=ticker,
        stock_name=stock_name,
        financial_data=financial_data,
        report_period=report_period,
        report_type=report_type,
    )
    
    return result


@router.post("/report-analysis/analyze", response_model=ReportAnalysisResponse)
async def analyze_report(request: AnalyzeRequest):
    """分析财报，提取关键数据"""
    report_period = request.report_period or "2025-12-31"
    
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            executor,
            _run_analysis,
            request.ticker,
            report_period,
            request.report_type,
        )
        
        highlights = []
        for h in result.get("highlights", []):
            if isinstance(h, dict):
                highlights.append(FinancialHighlight(**h))
        
        risks = []
        for r in result.get("risks", []):
            if isinstance(r, dict):
                risks.append(RiskFactor(**r))
        
        return ReportAnalysisResponse(
            ticker=result.get("ticker", request.ticker),
            report_period=result.get("report_period", report_period),
            report_type=result.get("report_type", request.report_type),
            analysis_date=result.get("analysis_date", ""),
            summary=result.get("summary", ""),
            revenue=result.get("revenue"),
            profit=result.get("profit"),
            cash_flow=result.get("cash_flow"),
            highlights=highlights,
            risks=risks,
            outlook=result.get("outlook"),
            recommendation=result.get("recommendation"),
            confidence=result.get("confidence", 0.5),
            error=result.get("error"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report-analysis/{ticker}")
async def get_analysis(ticker: str, period: Optional[str] = None):
    """获取已有的分析结果"""
    from investment.agents.tools.report_analyzer import (
        get_latest_analysis,
        get_all_analyses,
        load_cached_analysis,
    )
    
    if period:
        result = load_cached_analysis(ticker, period)
        if result:
            return result
        raise HTTPException(status_code=404, detail="分析结果不存在")
    
    latest = get_latest_analysis(ticker)
    if latest:
        return latest
    
    raise HTTPException(status_code=404, detail="暂无分析结果")


@router.get("/report-analysis/{ticker}/all")
async def get_all_analysis(ticker: str):
    """获取所有分析结果"""
    from investment.agents.tools.report_analyzer import get_all_analyses
    
    results = get_all_analyses(ticker)
    return {"ticker": ticker, "analyses": results, "total": len(results)}
