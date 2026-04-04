"""新闻获取模块 - 使用 AKShare 东方财富新闻接口"""
import akshare as ak
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import re
from cachetools import TTLCache
import threading

# 缓存：5分钟过期，最多100条
_cache = TTLCache(maxsize=100, ttl=300)
_cache_lock = threading.Lock()


@dataclass
class NewsArticle:
    title: str
    link: str
    source: str
    published: Optional[str] = None
    published_date: Optional[datetime] = None
    summary: Optional[str] = None
    thumbnail: Optional[str] = None


def get_stock_news(
    ticker: str,
    stock_name: str = "",
    market: str = "CN",
    limit: int = 10
) -> List[dict]:
    """获取股票相关新闻
    
    Args:
        ticker: 股票代码
        stock_name: 股票名称
        market: 市场 (CN, HK, US)
        limit: 返回数量
    
    Returns:
        新闻列表
    """
    cache_key = f"stock_news:{ticker}"
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key][:limit]
    
    result = []
    
    # 提取纯数字代码
    code = re.sub(r"[a-zA-Z.]", "", ticker)
    
    if market == "CN" and code:
        try:
            # 使用东方财富股票新闻
            df = ak.stock_news_em(symbol=code)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get("新闻标题", "") or row.get("标题", "")
                    link = row.get("新闻链接", "") or row.get("链接", "")
                    content = row.get("新闻内容", "") or row.get("内容", "")
                    pub_time = row.get("发布时间", "") or row.get("时间", "")
                    source = row.get("文章来源", "") or row.get("来源", "东方财富")
                    
                    # 解析时间
                    published_date = None
                    if pub_time:
                        try:
                            # 尝试解析多种时间格式
                            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m-%d %H:%M"]:
                                try:
                                    published_date = datetime.strptime(str(pub_time), fmt)
                                    break
                                except:
                                    continue
                        except:
                            pass
                    
                    result.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "published": str(pub_time) if pub_time else None,
                        "published_date": published_date.isoformat() if published_date else None,
                        "summary": content[:200] if content else None,
                        "thumbnail": None,
                    })
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
    
    # 缓存结果
    with _cache_lock:
        _cache[cache_key] = result
    
    return result[:limit]


def get_market_news(market: str = "CN", topic: str = "BUSINESS", limit: int = 20) -> List[dict]:
    """获取市场新闻
    
    Args:
        market: 市场 (CN, HK, US)
        topic: 话题
        limit: 返回数量
    """
    cache_key = f"market_news:{market}:{topic}"
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key][:limit]
    
    result = []
    
    if market == "CN":
        try:
            # 获取财经要闻
            df = ak.stock_info_global_em()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get("标题", "") or row.get("内容", "")
                    link = row.get("链接", "") or ""
                    pub_time = row.get("发布时间", "") or row.get("时间", "")
                    
                    result.append({
                        "title": title,
                        "link": link,
                        "source": "东方财富",
                        "published": str(pub_time) if pub_time else None,
                        "published_date": None,
                        "summary": None,
                        "thumbnail": None,
                    })
        except Exception as e:
            print(f"Error fetching market news: {e}")
    
    with _cache_lock:
        _cache[cache_key] = result
    
    return result[:limit]


def get_stock_research(ticker: str, limit: int = 10) -> List[dict]:
    """获取个股研报
    
    Args:
        ticker: 股票代码
        limit: 返回数量
    """
    cache_key = f"stock_research:{ticker}"
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key][:limit]
    
    result = []
    code = re.sub(r"[a-zA-Z.]", "", ticker)
    
    if code:
        try:
            # 获取个股研报
            df = ak.stock_research_report_em(symbol=code)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get("报告标题", "") or row.get("标题", "")
                    org = row.get("机构", "") or row.get("研究机构", "")
                    author = row.get("作者", "") or ""
                    rating = row.get("评级", "") or row.get("投资评级", "")
                    pub_date = row.get("日期", "") or row.get("发布日期", "")
                    
                    result.append({
                        "title": title,
                        "link": "",
                        "source": org,
                        "published": str(pub_date) if pub_date else None,
                        "published_date": None,
                        "summary": f"作者: {author}" if author else None,
                        "thumbnail": None,
                        "rating": rating,
                    })
        except Exception as e:
            print(f"Error fetching research for {ticker}: {e}")
    
    with _cache_lock:
        _cache[cache_key] = result
    
    return result[:limit]
