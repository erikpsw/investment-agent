"""
港股/美股财报 API 路由
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Any
from pydantic import BaseModel

from investment.data import SECEdgarClient, HKEXClient

router = APIRouter()

sec_client = SECEdgarClient()
hkex_client = HKEXClient()


class FilingInfo(BaseModel):
    ticker: str
    type: str
    date: str
    description: str = ""
    url: str = ""
    accession: str = ""


class CompanyInfo(BaseModel):
    ticker: str
    name: str = ""
    name_en: str = ""
    industry: str = ""
    sic: str = ""
    sic_description: str = ""
    fiscal_year_end: str = ""
    exchanges: List[str] = []
    error: str = ""


class FilingsResponse(BaseModel):
    ticker: str
    market: str
    filings: List[FilingInfo]


# ==================== 美股财报 ====================

@router.get("/us/filings/{ticker}", response_model=FilingsResponse)
async def get_us_filings(
    ticker: str,
    filing_type: str = Query("10-K", description="Filing type: 10-K, 10-Q, 8-K"),
    limit: int = Query(10, ge=1, le=50),
):
    """获取美股财报列表（SEC EDGAR）"""
    try:
        filings = sec_client.get_filings_list(ticker, filing_type, limit)
        
        return FilingsResponse(
            ticker=ticker.upper(),
            market="US",
            filings=[
                FilingInfo(
                    ticker=f["ticker"],
                    type=f["type"],
                    date=f["date"],
                    description=f["description"],
                    url=f["url"],
                    accession=f.get("accession", ""),
                )
                for f in filings
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/us/annual/{ticker}", response_model=FilingsResponse)
async def get_us_annual_reports(
    ticker: str,
    limit: int = Query(5, ge=1, le=20),
):
    """获取美股年报列表 (10-K)"""
    try:
        filings = sec_client.get_annual_reports(ticker, limit)
        
        return FilingsResponse(
            ticker=ticker.upper(),
            market="US",
            filings=[
                FilingInfo(
                    ticker=f["ticker"],
                    type=f["type"],
                    date=f["date"],
                    description=f["description"],
                    url=f["url"],
                    accession=f.get("accession", ""),
                )
                for f in filings
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/us/quarterly/{ticker}", response_model=FilingsResponse)
async def get_us_quarterly_reports(
    ticker: str,
    limit: int = Query(8, ge=1, le=20),
):
    """获取美股季报列表 (10-Q)"""
    try:
        filings = sec_client.get_quarterly_reports(ticker, limit)
        
        return FilingsResponse(
            ticker=ticker.upper(),
            market="US",
            filings=[
                FilingInfo(
                    ticker=f["ticker"],
                    type=f["type"],
                    date=f["date"],
                    description=f["description"],
                    url=f["url"],
                    accession=f.get("accession", ""),
                )
                for f in filings
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/us/company/{ticker}")
async def get_us_company_info(ticker: str):
    """获取美股公司信息"""
    try:
        info = sec_client.get_company_info(ticker)
        if "error" in info:
            raise HTTPException(status_code=404, detail=info["error"])
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 港股财报 ====================

@router.get("/hk/company/{ticker}")
async def get_hk_company_info(ticker: str):
    """获取港股公司信息"""
    try:
        info = hkex_client.get_company_info(ticker)
        if "error" in info:
            raise HTTPException(status_code=404, detail=info["error"])
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hk/financial/{ticker}")
async def get_hk_financial_report(
    ticker: str,
    indicator: str = Query("年度", description="报告类型: 年度, 中期"),
):
    """获取港股财务报告数据"""
    try:
        df = hkex_client.get_financial_report(ticker, indicator)
        
        if df.empty:
            return {"ticker": ticker, "data": [], "message": "No data available"}
        
        # 转换为字典列表
        records = df.to_dict(orient="records")
        
        # 清理数据
        cleaned = []
        for r in records:
            cleaned_record = {}
            for k, v in r.items():
                if v is not None and str(v) != "nan":
                    cleaned_record[k] = v
            cleaned.append(cleaned_record)
        
        return {
            "ticker": ticker,
            "indicator": indicator,
            "columns": df.columns.tolist(),
            "data": cleaned[:100],  # 限制返回数量
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hk/indicators/{ticker}")
async def get_hk_financial_indicators(ticker: str):
    """获取港股财务分析指标"""
    try:
        df = hkex_client.get_financial_indicators(ticker)
        
        if df.empty:
            return {"ticker": ticker, "data": [], "message": "No data available"}
        
        records = df.to_dict(orient="records")
        
        # 清理数据
        cleaned = []
        for r in records:
            cleaned_record = {}
            for k, v in r.items():
                if v is not None and str(v) != "nan":
                    cleaned_record[k] = v
            cleaned.append(cleaned_record)
        
        return {
            "ticker": ticker,
            "columns": df.columns.tolist(),
            "data": cleaned,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hk/announcements/{ticker}", response_model=FilingsResponse)
async def get_hk_announcements(
    ticker: str,
    category: str = Query("all", description="类型: annual, interim, results, all"),
    limit: int = Query(10, ge=1, le=50),
):
    """获取港股公告列表"""
    try:
        announcements = hkex_client.get_announcements(ticker, category, limit)
        
        return FilingsResponse(
            ticker=ticker,
            market="HK",
            filings=[
                FilingInfo(
                    ticker=a["ticker"],
                    type=a.get("type", "other"),
                    date=a.get("date", ""),
                    description=a.get("title", ""),
                    url=a.get("url", ""),
                )
                for a in announcements
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hk/valuation/{ticker}")
async def get_hk_valuation(ticker: str):
    """获取港股估值指标"""
    try:
        data = hkex_client.get_hk_indicator_eniu(ticker)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
