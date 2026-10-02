"""新闻获取模块 - 支持 A股/港股/美股"""
import akshare as ak
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import re
import httpx
from cachetools import TTLCache
import threading

_cache = TTLCache(maxsize=100, ttl=300)
_cache_lock = threading.Lock()
_stock_news_locks = [threading.Lock() for _ in range(32)]


@dataclass
class NewsArticle:
    title: str
    link: str
    source: str
    published: Optional[str] = None
    published_date: Optional[datetime] = None
    summary: Optional[str] = None
    thumbnail: Optional[str] = None


def _parse_time(pub_time) -> Optional[datetime]:
    if not pub_time:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m-%d %H:%M", "%Y/%m/%d %H:%M"]:
        try:
            return datetime.strptime(str(pub_time), fmt)
        except (ValueError, TypeError):
            continue
    return None


def _fetch_cn_stock_news(code: str) -> List[dict]:
    try:
        df = ak.stock_news_em(symbol=code)
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            title = row.get("新闻标题", "") or row.get("标题", "")
            link = row.get("新闻链接", "") or row.get("链接", "")
            content = row.get("新闻内容", "") or row.get("内容", "")
            pub_time = row.get("发布时间", "") or row.get("时间", "")
            source = row.get("文章来源", "") or row.get("来源", "东方财富")
            pd = _parse_time(pub_time)
            result.append({
                "title": title, "link": link, "source": source,
                "published": str(pub_time) if pub_time else None,
                "published_date": pd.isoformat() if pd else None,
                "summary": content[:200] if content else None,
                "thumbnail": None,
            })
        return result
    except Exception as e:
        print(f"[News] CN fetch error: {e}")
        return []


def _fetch_keyword_news(keyword: str) -> List[dict]:
    """通用关键词新闻搜索 - 使用 AKShare stock_news_em"""
    result = []
    try:
        df = ak.stock_news_em(symbol=keyword)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                title = row.get("新闻标题", "") or row.get("标题", "")
                link = row.get("新闻链接", "") or row.get("链接", "")
                content = row.get("新闻内容", "") or row.get("内容", "")
                pub_time = row.get("发布时间", "") or row.get("时间", "")
                source = row.get("文章来源", "") or row.get("来源", "东方财富")
                pd = _parse_time(pub_time)
                result.append({
                    "title": title, "link": link, "source": source,
                    "published": str(pub_time) if pub_time else None,
                    "published_date": pd.isoformat() if pd else None,
                    "summary": content[:200] if content else None,
                    "thumbnail": None,
                })
    except Exception as e:
        print(f"[News] Keyword search error for '{keyword}': {e}")
    return result


def _fetch_hk_stock_news(ticker: str, stock_name: str) -> List[dict]:
    """港股新闻 - 用公司名作为关键词搜索"""
    keyword = stock_name or re.sub(r"[a-zA-Z.]", "", ticker)
    return _fetch_keyword_news(keyword)


def _fetch_us_stock_news(ticker: str, stock_name: str) -> List[dict]:
    """Prefer ticker-specific company news; validate entity matches before fallback."""
    import yfinance as yf
    items = []
    try:
        for row in yf.Ticker(ticker.upper()).get_news(count=30):
            content = row.get("content") or row
            canonical = content.get("canonicalUrl") or content.get("clickThroughUrl") or {}
            provider = content.get("provider") or {}
            published = content.get("pubDate") or content.get("displayTime")
            items.append({
                "title": content.get("title", ""),
                "link": canonical.get("url", "") if isinstance(canonical, dict) else str(canonical),
                "source": provider.get("displayName", "Yahoo Finance") if isinstance(provider, dict) else str(provider),
                "published": published,
                "published_date": published,
                "summary": content.get("summary") or content.get("description"),
                "thumbnail": None,
            })
    except Exception as exc:
        print(f"[News] US company feed unavailable: {type(exc).__name__}")
    relevant = _relevant_stock_news(items, ticker, stock_name, "US")
    if relevant:
        return relevant
    aliases = _company_aliases(ticker, stock_name, "US")
    keyword = aliases[-1] if aliases else ticker
    return _fetch_keyword_news(keyword)


def _company_aliases(ticker: str, stock_name: str, market: str) -> List[str]:
    """Company-specific aliases only; never generic industry or corporate words."""
    name = (stock_name or "").strip()
    aliases = [name] if name else []
    short = re.sub(r"(?i)\b(incorporated|corporation|holdings?|limited|inc|corp|ltd|plc|co)\b[.,]?", "", name)
    short = re.sub(r"(?:股份有限公司|股份公司|有限公司|控股有限公司|集团有限公司|控股|集团)$", "", short.strip())
    short = re.sub(r"(?i)[-－](?:SW|W|S|B|H|U)$", "", short).strip(" .,，")
    if len(short) >= 2:
        aliases.append(short)
    code = re.sub(r"^(sh|sz|bj|hk)", "", ticker, flags=re.I).replace(".HK", "")
    if market != "US" and code:
        aliases.append(code)
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _relevant_stock_news(items: List[dict], ticker: str, stock_name: str, market: str) -> List[dict]:
    aliases = _company_aliases(ticker, stock_name, market)
    result, seen = [], set()
    for item in items:
        title = str(item.get("title") or "")
        text = title + " " + str(item.get("summary") or "")
        match = None
        for alias in aliases:
            # Latin aliases need boundaries: CAT must not match 'category'.
            pattern = re.escape(alias)
            if re.fullmatch(r"[\w .,&'-]+", alias, flags=re.ASCII):
                pattern = r"(?<![A-Za-z0-9])" + pattern + r"(?![A-Za-z0-9])"
            if re.search(pattern, text, re.I):
                match = alias
                break
        if not match and market == "US":
            # Short ambiguous symbols need an explicit exchange/ticker marker.
            symbol = re.escape(ticker.upper())
            pattern = (r"(?i)(?:NASDAQ|NYSE|AMEX|ticker)\s*[:：]\s*" + symbol + r"(?![A-Za-z0-9])|\$" + symbol + r"(?![A-Za-z0-9])")
            if re.search(pattern, text) or (len(ticker) >= 4 and re.search(r"(?<![A-Za-z0-9])" + symbol + r"(?![A-Za-z0-9])", text)):
                match = ticker.upper()
        key = str(item.get("link") or title).strip()
        if match and title and key and key not in seen:
            seen.add(key)
            result.append({**item, "matched_entity": match})
    result.sort(key=lambda item: str(item.get("published_date") or item.get("published") or ""), reverse=True)
    return result


def get_stock_news(
    ticker: str,
    stock_name: str = "",
    market: str = "CN",
    limit: int = 10
) -> List[dict]:
    market = market.upper()
    if not stock_name.strip():
        try:
            from .stock_search import resolve_stock
            identity = resolve_stock(ticker)
            stock_name = str((identity or {}).get("name") or "")
        except Exception:
            # Preserve ticker-based matching when company lookup is unavailable.
            stock_name = ""
    cache_key = f"stock_news:v2:{market}:{ticker}:{stock_name.strip()}"
    with _stock_news_locks[hash(cache_key) % len(_stock_news_locks)]:
        with _cache_lock:
            if cache_key in _cache:
                return _cache[cache_key][:limit]
    
        code = re.sub(r"[a-zA-Z.]", "", ticker)
    
        if market == "CN" and code:
            result = _fetch_cn_stock_news(code)
        elif market == "HK":
            result = _fetch_hk_stock_news(ticker, stock_name)
        elif market == "US":
            result = _fetch_us_stock_news(ticker, stock_name)
        else:
            result = []
    
        result = _relevant_stock_news(result, ticker, stock_name, market)
        with _cache_lock:
            _cache[cache_key] = result
    
        return result[:limit]


def get_market_news(market: str = "CN", topic: str = "BUSINESS", limit: int = 20) -> List[dict]:
    cache_key = f"market_news:{market}:{topic}"
    with _cache_lock:
        if cache_key in _cache:
            return _cache[cache_key][:limit]
    
    result = []
    
    try:
        if market == "CN":
            df = ak.stock_info_global_em()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get("标题", "") or row.get("内容", "")
                    link = row.get("链接", "") or ""
                    pub_time = row.get("发布时间", "") or row.get("时间", "")
                    result.append({
                        "title": title, "link": link, "source": "东方财富",
                        "published": str(pub_time) if pub_time else None,
                        "published_date": None, "summary": None, "thumbnail": None,
                    })
        elif market in ("HK", "US"):
            # 港股/美股用全球财经要闻
            df = ak.stock_info_global_em()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get("标题", "") or row.get("内容", "")
                    link = row.get("链接", "") or ""
                    pub_time = row.get("发布时间", "") or row.get("时间", "")
                    result.append({
                        "title": title, "link": link, "source": "财经要闻",
                        "published": str(pub_time) if pub_time else None,
                        "published_date": None, "summary": None, "thumbnail": None,
                    })
    except Exception as e:
        print(f"[News] Market news error for {market}: {e}")
    
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
