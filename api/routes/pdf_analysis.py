"""PDF 财报分析 API"""
import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=2)


class PDFAnalysisRequest(BaseModel):
    ticker: str
    stock_name: Optional[str] = None
    pdf_url: str
    report_title: str
    focus_sections: Optional[List[str]] = None


class SearchRequest(BaseModel):
    ticker: str
    report_title: str
    query: str


def _analyze_pdf(ticker: str, stock_name: str, pdf_url: str, report_title: str, focus_sections: Optional[List[str]]):
    from investment.agents.tools.pdf_analyzer import analyze_pdf_report
    return analyze_pdf_report(ticker, stock_name, pdf_url, report_title, focus_sections)


def _search_report(ticker: str, report_title: str, query: str):
    from investment.agents.tools.pdf_analyzer import search_in_report
    return search_in_report(ticker, report_title, query)


def _get_cached(ticker: str):
    from investment.agents.tools.pdf_analyzer import get_cached_reports
    return get_cached_reports(ticker)


@router.post("/pdf-analysis/analyze")
async def analyze_pdf(request: PDFAnalysisRequest):
    """分析 PDF 财报"""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            executor,
            _analyze_pdf,
            request.ticker,
            request.stock_name or request.ticker,
            request.pdf_url,
            request.report_title,
            request.focus_sections,
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf-analysis/search")
async def search_pdf(request: SearchRequest):
    """在财报中搜索关键词"""
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            executor,
            _search_report,
            request.ticker,
            request.report_title,
            request.query,
        )
        
        return {"results": results, "total": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf-analysis/{ticker}/cached")
async def get_cached_reports(ticker: str):
    """获取已缓存的财报列表"""
    loop = asyncio.get_event_loop()
    try:
        reports = await loop.run_in_executor(
            executor,
            _get_cached,
            ticker,
        )
        
        return {"ticker": ticker, "reports": reports, "total": len(reports)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
