"""港股/A股财报披露文件API - 获取PDF直链"""
import re
import logging
import asyncio
from typing import List, Optional, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from cachetools import TTLCache

router = APIRouter()
logger = logging.getLogger(__name__)

# 线程池用于运行Playwright
_executor = ThreadPoolExecutor(max_workers=2)

# PDF缓存: 30分钟TTL, 最多100个股票
pdf_cache: TTLCache = TTLCache(maxsize=100, ttl=1800)


class DisclosureItem(BaseModel):
    title: str
    url: str
    date: str
    size: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None


class DisclosureResponse(BaseModel):
    ticker: str
    market: str
    company_name: Optional[str] = None
    documents: List[DisclosureItem]
    source_url: str
    cached: bool = False


# 港股公司名称映射
HK_COMPANY_NAMES: Dict[str, str] = {
    "00700": "腾讯控股",
    "09988": "阿里巴巴-SW",
    "03690": "美团-W",
    "09618": "京东集团-SW",
    "09888": "百度集团-SW",
    "01024": "快手-W",
    "06618": "京东健康",
    "09999": "网易-S",
    "00981": "中芯国际",
    "02318": "中国平安",
    "00941": "中国移动",
    "00883": "中海油",
    "01810": "小米集团-W",
    "02020": "安踏体育",
    "06862": "海底捞",
}


def _extract_hk_code(ticker: str) -> str:
    """提取港股代码 hk00700 -> 00700"""
    code = ticker.lower().replace("hk", "").replace(".hk", "")
    return code.zfill(5)


def _fetch_hkex_with_subprocess(code: str, limit: int = 20) -> List[DisclosureItem]:
    """使用subprocess运行独立的Playwright爬取脚本"""
    import subprocess
    import json
    import sys
    import os
    
    documents = []
    
    try:
        # 获取爬虫脚本路径
        script_path = os.path.join(os.path.dirname(__file__), "disclosure_crawler.py")
        
        # 使用subprocess运行爬虫脚本
        result = subprocess.run(
            [sys.executable, script_path, code, str(limit)],
            capture_output=True,
            text=True,
            timeout=60,  # 60秒超时
        )
        
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            for item in data:
                documents.append(DisclosureItem(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    date=item.get("date", ""),
                    size=item.get("size"),
                    category=item.get("category"),
                    source=item.get("source", "HKEXnews"),
                ))
        else:
            logger.warning(f"Crawler script error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error(f"Crawler timeout for {code}")
    except Exception as e:
        logger.error(f"Subprocess error for {code}: {e}")
    
    # 如果没有获取到任何文档，返回备用链接
    if not documents:
        return _get_fallback_links(code)
    
    return documents


def _get_fallback_links(code: str) -> List[DisclosureItem]:
    """当Playwright失败时返回备用链接"""
    documents = []
    
    # 披露易搜索链接
    documents.append(DisclosureItem(
        title="查看财报PDF (披露易)",
        url=f"https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=ZH&category=40100&category=40200&market=SEHK&searchType=1&stockCode={code}",
        date=datetime.now().strftime("%Y-%m-%d"),
        category="financial",
        source="HKEXnews",
    ))
    
    # 特定公司的官方IR链接
    ir_links = {
        "00700": "https://www.tencent.com/zh-cn/investors/financial-reports.html",
        "09988": "https://www.alibabagroup.com/zh-HK/ir-financial-reports",
        "03690": "https://www.meituan.com/investor_relations",
        "09618": "https://ir.jd.com/financial-information/quarterly-results",
        "09888": "https://ir.baidu.com/financial-information/quarterly-results",
        "01024": "https://ir.kuaishou.com/financial-information",
        "01810": "https://ir.mi.com/financial-information",
    }
    
    if code in ir_links:
        documents.append(DisclosureItem(
            title="财报下载 (官网)",
            url=ir_links[code],
            date=datetime.now().strftime("%Y-%m-%d"),
            category="ir",
            source="Official",
        ))
    
    return documents


async def _fetch_hkex_documents(code: str, category: str = "all", limit: int = 20) -> tuple[List[DisclosureItem], bool]:
    """获取港股财报PDF直链
    
    返回: (documents, from_cache)
    """
    cache_key = f"hk_{code}_{category}"
    
    # 检查缓存
    if cache_key in pdf_cache:
        logger.info(f"Cache hit for {cache_key}")
        return pdf_cache[cache_key], True
    
    # 使用subprocess运行独立的Playwright爬取脚本
    logger.info(f"Fetching PDFs for {code} with Playwright subprocess...")
    loop = asyncio.get_event_loop()
    documents = await loop.run_in_executor(
        _executor, 
        lambda: _fetch_hkex_with_subprocess(code, limit)
    )
    
    # 缓存结果（只缓存成功获取到PDF直链的结果）
    if documents and any(doc.url.endswith('.pdf') for doc in documents):
        pdf_cache[cache_key] = documents
    
    return documents, False


def _fetch_cn_documents(ticker: str, category: str = "all") -> List[DisclosureItem]:
    """从东方财富/巨潮获取A股财报链接"""
    code = ticker.lower().replace("sh", "").replace("sz", "")
    market = "sh" if ticker.lower().startswith("sh") else "sz"
    
    documents = []
    
    try:
        # 东方财富财报链接
        ef_url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code={market.upper()}{code}"
        
        # 巨潮资讯网
        cninfo_url = f"http://www.cninfo.com.cn/new/disclosure/stock?stockCode={code}&orgId="
        
        # 暂时返回固定链接
        documents.append(DisclosureItem(
            title="财务分析 (东方财富)",
            url=ef_url,
            date=datetime.now().strftime("%Y-%m-%d"),
            category="financial",
        ))
        
    except Exception as e:
        print(f"[CNInfo] Error: {e}")
    
    return documents


@router.get("/disclosure/{ticker}", response_model=DisclosureResponse)
async def get_disclosure_documents(
    ticker: str,
    category: str = Query("annual", description="文档类型: annual(年报), interim(中期), quarterly(季报), all(全部)"),
    limit: int = Query(20, ge=1, le=50),
):
    """获取上市公司财报/公告PDF直链
    
    支持：
    - 港股：hk00700, 00700.HK
    - A股：sh600519, sz000001
    """
    ticker_lower = ticker.lower()
    
    if ticker_lower.startswith("hk") or ticker.endswith(".HK"):
        # 港股 - 使用异步函数
        code = _extract_hk_code(ticker)
        documents, cached = await _fetch_hkex_documents(code, category, limit)
        
        return DisclosureResponse(
            ticker=ticker,
            market="HK",
            company_name=HK_COMPANY_NAMES.get(code),
            documents=documents[:limit],
            source_url=f"https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=ZH&stockCode={code}",
            cached=cached,
        )
    
    elif ticker_lower.startswith("sh") or ticker_lower.startswith("sz"):
        # A股
        documents = _fetch_cn_documents(ticker, category)
        
        code = ticker_lower.replace("sh", "").replace("sz", "")
        return DisclosureResponse(
            ticker=ticker,
            market="CN",
            documents=documents[:limit],
            source_url=f"http://www.cninfo.com.cn/new/fulltextSearch/full?searchkey={code}",
        )
    
    else:
        # 美股
        symbol = ticker.upper()
        return DisclosureResponse(
            ticker=ticker,
            market="US",
            documents=[
                DisclosureItem(
                    title="SEC Filings (10-K, 10-Q)",
                    url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={symbol}&type=10-&dateb=&owner=include&count=40",
                    date=datetime.now().strftime("%Y-%m-%d"),
                    category="sec",
                ),
                DisclosureItem(
                    title="Yahoo Finance - Financials",
                    url=f"https://finance.yahoo.com/quote/{symbol}/financials",
                    date=datetime.now().strftime("%Y-%m-%d"),
                    category="financial",
                ),
            ],
            source_url=f"https://www.sec.gov/cgi-bin/browse-edgar?company={symbol}&CIK=&type=10-K&owner=include&count=40&action=getcompany",
        )


@router.delete("/disclosure/cache")
async def clear_disclosure_cache():
    """清空PDF缓存"""
    pdf_cache.clear()
    return {"message": "Cache cleared"}
