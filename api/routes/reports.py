"""财报相关 API 路由"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import asyncio

from investment.reports.downloader import ReportDownloader

router = APIRouter()
downloader = ReportDownloader()
executor = ThreadPoolExecutor(max_workers=2)


class ReportItem(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    title: str
    time: Optional[str] = None
    url: Optional[str] = None
    announcement_url: Optional[str] = None


class ReportListResponse(BaseModel):
    ticker: str
    reports: List[ReportItem]
    total: int


class FinancialDataResponse(BaseModel):
    stock_code: str
    abstract: Optional[Any] = None
    income: Optional[Any] = None
    balance: Optional[Any] = None
    cashflow: Optional[Any] = None


@router.get("/reports/{ticker}", response_model=ReportListResponse)
async def get_reports(
    ticker: str,
    report_type: str = Query("年报", description="报告类型：年报、半年报、季报"),
    years: int = Query(3, description="搜索多少年内的报告", ge=1, le=10),
):
    """获取股票财报公告列表"""
    loop = asyncio.get_event_loop()
    
    try:
        reports = await loop.run_in_executor(
            executor,
            downloader.search_reports,
            ticker,
            report_type,
            years,
        )
        
        if reports and len(reports) == 1 and "error" in reports[0]:
            raise HTTPException(status_code=500, detail=reports[0]["error"])
        
        items = [
            ReportItem(
                stock_code=r.get("stock_code", ""),
                stock_name=r.get("stock_name"),
                title=r.get("title", ""),
                time=str(r.get("time", "")) if r.get("time") else None,
                url=r.get("url"),
                announcement_url=r.get("announcement_url"),
            )
            for r in reports
            if "error" not in r
        ]
        
        return ReportListResponse(
            ticker=ticker,
            reports=items,
            total=len(items),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{ticker}/data", response_model=FinancialDataResponse)
async def get_financial_data(ticker: str):
    """获取财务数据摘要（利润表、资产负债表、现金流量表）"""
    loop = asyncio.get_event_loop()
    
    try:
        data = await loop.run_in_executor(
            executor,
            downloader.get_financial_data,
            ticker,
        )
        
        return FinancialDataResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
