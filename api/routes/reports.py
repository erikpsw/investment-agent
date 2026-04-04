"""财报相关 API 路由"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import asyncio

from investment.reports.downloader import ReportDownloader
from investment.data.sec_edgar_client import SECEdgarClient
from investment.data.hkex_client import HKEXClient

router = APIRouter()
downloader = ReportDownloader()
sec_client = SECEdgarClient()
hkex_client = HKEXClient()
executor = ThreadPoolExecutor(max_workers=2)


def _is_us_stock(ticker: str) -> bool:
    """判断是否为美股"""
    ticker_upper = ticker.upper()
    if ticker_upper.startswith(("SH", "SZ", "HK")):
        return False
    if ticker.isdigit():
        return False
    return True


def _is_hk_stock(ticker: str) -> bool:
    """判断是否为港股"""
    ticker_lower = ticker.lower()
    return ticker_lower.startswith("hk") or ticker.endswith(".HK")


class ReportItem(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    title: str
    time: Optional[str] = None
    url: Optional[str] = None
    announcement_url: Optional[str] = None
    has_pdf: bool = True  # 是否有PDF下载
    period: Optional[str] = None  # 报告期间，用于深度分析


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
    report_type: str = Query("年报", description="报告类型：年报、半年报、季报、Q1、Q3"),
    years: int = Query(2, description="搜索多少年内的报告", ge=1, le=5),
):
    """获取股票财报公告列表
    
    支持 A股、港股、美股
    - A股: 使用巨潮资讯网
    - 港股: 使用 AKShare/东方财富
    - 美股: 使用 SEC EDGAR
    """
    loop = asyncio.get_event_loop()
    
    try:
        # 判断市场类型
        if _is_us_stock(ticker):
            # 美股: 使用 SEC EDGAR
            items = await _get_us_reports(ticker, report_type, years)
        elif _is_hk_stock(ticker):
            # 港股: 使用 HKEX/AKShare
            items = await _get_hk_reports(ticker, report_type, years)
        else:
            # A股: 使用原有逻辑
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


async def _get_us_reports(ticker: str, report_type: str, years: int) -> List[ReportItem]:
    """获取美股财报列表"""
    loop = asyncio.get_event_loop()
    
    # 映射报告类型
    type_map = {
        "年报": "10-K",
        "半年报": "10-Q",  # 美股没有半年报，用季报代替
        "季报": "10-Q",
        "Q1": "10-Q",
        "Q3": "10-Q",
    }
    filing_type = type_map.get(report_type, "10-K")
    limit = years * (4 if filing_type == "10-Q" else 1)
    
    filings = await loop.run_in_executor(
        executor,
        sec_client.get_filings_list,
        ticker,
        filing_type,
        limit,
    )
    
    items = []
    for f in filings:
        items.append(ReportItem(
            stock_code=f.get("ticker", ticker),
            stock_name=None,
            title=f"{f.get('type', '')} - {f.get('description', '')}",
            time=f.get("date"),
            url=f.get("url"),
            announcement_url=f.get("url"),
        ))
    
    return items


async def _get_hk_reports(ticker: str, report_type: str, years: int) -> List[ReportItem]:
    """获取港股财报列表"""
    loop = asyncio.get_event_loop()
    
    # 映射报告类型
    indicator_map = {
        "年报": "年度",
        "半年报": "中期",
        "季报": "年度",  # 港股没有季报，使用年度
        "Q1": "中期",
        "Q3": "中期",
    }
    indicator = indicator_map.get(report_type, "年度")
    limit = years * 2  # 每年获取几份
    
    # 使用新的方法从财务数据提取报告列表
    reports = await loop.run_in_executor(
        executor,
        hkex_client.get_available_reports,
        ticker,
        indicator,
        limit,
    )
    
    items = []
    for r in reports:
        items.append(ReportItem(
            stock_code=r.get("ticker", ticker),
            stock_name=None,
            title=r.get("title", ""),
            time=r.get("date"),
            url=r.get("url"),
            announcement_url=r.get("announcement_url"),
            has_pdf=r.get("has_pdf", False),
            period=r.get("period"),
        ))
    
    return items


@router.get("/reports/{ticker}/data", response_model=FinancialDataResponse)
async def get_financial_data(ticker: str):
    """获取财务数据摘要（利润表、资产负债表、现金流量表）
    
    支持 A股、港股、美股
    """
    loop = asyncio.get_event_loop()
    
    try:
        if _is_us_stock(ticker):
            # 美股: 使用 SEC EDGAR 公司信息
            company_info = await loop.run_in_executor(
                executor,
                sec_client.get_company_info,
                ticker,
            )
            return FinancialDataResponse(
                stock_code=ticker,
                abstract={
                    "company_name": company_info.get("name"),
                    "sic": company_info.get("sic"),
                    "sic_description": company_info.get("sic_description"),
                    "fiscal_year_end": company_info.get("fiscal_year_end"),
                    "exchanges": company_info.get("exchanges", []),
                },
            )
        elif _is_hk_stock(ticker):
            # 港股: 使用 AKShare 财务数据
            company_info = await loop.run_in_executor(
                executor,
                hkex_client.get_company_info,
                ticker,
            )
            indicators = await loop.run_in_executor(
                executor,
                hkex_client.get_financial_indicators,
                ticker,
            )
            
            abstract = {
                "company_name": company_info.get("name"),
                "listing_date": company_info.get("listing_date"),
                "industry": company_info.get("industry"),
            }
            
            # 添加财务指标
            if indicators is not None and not indicators.empty:
                latest = indicators.iloc[0].to_dict()
                abstract.update({
                    "roe": latest.get("ROE"),
                    "gross_margin": latest.get("GROSS_PROFIT_RATIO"),
                    "net_margin": latest.get("NET_PROFIT_RATIO"),
                })
            
            return FinancialDataResponse(
                stock_code=ticker,
                abstract=abstract,
            )
        else:
            # A股: 使用原有逻辑
            data = await loop.run_in_executor(
                executor,
                downloader.get_financial_data,
                ticker,
            )
            return FinancialDataResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
