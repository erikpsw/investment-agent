"""新闻 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
import asyncio

router = APIRouter()
executor = ThreadPoolExecutor(max_workers=2)


class NewsItem(BaseModel):
    title: str
    link: str
    source: str
    published: Optional[str] = None
    published_date: Optional[str] = None
    summary: Optional[str] = None
    thumbnail: Optional[str] = None


class NewsResponse(BaseModel):
    ticker: Optional[str] = None
    stock_name: Optional[str] = None
    market: str
    news: List[NewsItem]


@router.get("/news/{ticker}", response_model=NewsResponse)
async def get_stock_news(
    ticker: str,
    stock_name: str = Query("", description="股票名称"),
    market: str = Query("CN", description="市场 (CN, HK, US)"),
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
):
    """获取股票相关新闻"""
    from investment.data.news_fetcher import get_stock_news as fetch_news
    
    loop = asyncio.get_event_loop()
    
    def fetch():
        return fetch_news(
            ticker=ticker,
            stock_name=stock_name,
            market=market,
            limit=limit,
        )
    
    news = await loop.run_in_executor(executor, fetch)
    
    return NewsResponse(
        ticker=ticker,
        stock_name=stock_name or None,
        market=market,
        news=[NewsItem(**item) for item in news],
    )


@router.get("/news/market/{market}", response_model=NewsResponse)
async def get_market_news(
    market: str,
    topic: str = Query("BUSINESS", description="话题 (BUSINESS, TECHNOLOGY, etc.)"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
):
    """获取市场新闻"""
    from investment.data.news_fetcher import get_market_news as fetch_market
    
    loop = asyncio.get_event_loop()
    
    def fetch():
        return fetch_market(
            market=market,
            topic=topic,
            limit=limit,
        )
    
    news = await loop.run_in_executor(executor, fetch)
    
    return NewsResponse(
        market=market,
        news=[NewsItem(**item) for item in news],
    )
