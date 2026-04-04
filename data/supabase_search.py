"""
Supabase 股票搜索 - 使用 PostgreSQL 全文搜索，比本地 pandas 快 10x+
"""
import os
from typing import Any, Optional, List, Dict
from functools import lru_cache


_supabase_client = None


def get_supabase_client():
    """获取 Supabase 客户端（单例）"""
    global _supabase_client
    if _supabase_client is None:
        try:
            from supabase import create_client
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_ANON_KEY")
            if url and key:
                _supabase_client = create_client(url, key)
        except ImportError:
            print("[SupabaseSearch] supabase-py not installed, falling back to local search")
        except Exception as e:
            print(f"[SupabaseSearch] Failed to create client: {e}")
    return _supabase_client


class SupabaseStockSearch:
    """使用 Supabase PostgreSQL 的股票搜索器"""
    
    def __init__(self):
        self._client = None
        self._fallback = None
    
    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase_client()
        return self._client
    
    @property
    def fallback(self):
        """本地搜索作为后备"""
        if self._fallback is None:
            from investment.data.stock_search import StockSearch
            self._fallback = StockSearch()
        return self._fallback
    
    def search(self, query: str, market: str = "all", limit: int = 10) -> List[Dict[str, Any]]:
        """搜索股票 - 优先使用 Supabase，失败则回退到本地"""
        if not self.client:
            return self.fallback.search(query, market, limit)
        
        try:
            return self._search_supabase(query, market, limit)
        except Exception as e:
            print(f"[SupabaseSearch] Search error: {e}, falling back to local")
            return self.fallback.search(query, market, limit)
    
    # 中文别名映射（用于搜索港股/美股）
    ALIASES = {
        "腾讯": "TENCENT",
        "阿里": "ALIBABA",
        "阿里巴巴": "ALIBABA",
        "美团": "MEITUAN",
        "京东": "JD",
        "百度": "BAIDU",
        "小米": "XIAOMI",
        "网易": "NETEASE",
        "拼多多": "PDD",
        "蔚来": "NIO",
        "理想": "LI",
        "小鹏": "XPENG",
        "哔哩哔哩": "BILIBILI",
        "B站": "BILIBILI",
        "苹果": "APPLE",
        "谷歌": "GOOGLE",
        "微软": "MICROSOFT",
        "亚马逊": "AMAZON",
        "特斯拉": "TESLA",
        "英伟达": "NVIDIA",
        "脸书": "META",
        "奈飞": "NETFLIX",
        "英特尔": "INTEL",
        "高通": "QUALCOMM",
        "汇丰": "HSBC",
        "友邦": "AIA",
        "港交所": "HKEX",
        "中移动": "CHINA MOBILE",
        "中国移动": "CHINA MOBILE",
        "比亚迪": "BYD",
    }
    
    def _search_supabase(self, query: str, market: str, limit: int) -> List[Dict[str, Any]]:
        """使用 Supabase 搜索"""
        query = query.strip()
        if not query:
            return []
        
        # 检查别名
        search_terms = [query.lower()]
        alias = self.ALIASES.get(query)
        if alias:
            search_terms.append(alias.lower())
        
        all_results = []
        
        for term in search_terms:
            builder = self.client.table("stocks").select("*")
            
            # 市场过滤
            if market != "all":
                builder = builder.eq("market", market.upper())
            
            # 搜索条件：名称、代码、拼音
            builder = builder.or_(
                f"name.ilike.%{term}%,"
                f"ticker.ilike.%{term}%,"
                f"code.ilike.%{term}%,"
                f"pinyin.ilike.%{term}%"
            )
            
            builder = builder.limit(limit)
            
            response = builder.execute()
            
            for row in response.data:
                result = {
                    "code": row.get("ticker", ""),
                    "name": row.get("name", ""),
                    "market": row.get("market", ""),
                    "display": f"{row.get('name', '')} ({row.get('ticker', '')})",
                    "exchange": row.get("exchange", ""),
                }
                # 去重
                if result not in all_results:
                    all_results.append(result)
        
        return self._rank_results(all_results, query)[:limit]
    
    def resolve(self, query: str) -> Optional[Dict[str, Any]]:
        """解析用户输入，返回最匹配的股票"""
        if not self.client:
            return self.fallback.resolve(query)
        
        try:
            results = self.search(query, limit=1)
            return results[0] if results else None
        except Exception as e:
            print(f"[SupabaseSearch] Resolve error: {e}")
            return self.fallback.resolve(query)
    
    def _rank_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """对结果排序：精确匹配 > 前缀匹配 > 包含匹配"""
        query_lower = query.lower()
        
        def score(item):
            name = item.get("name", "").lower()
            code = item.get("code", "").lower()
            
            if name == query_lower or code == query_lower:
                return (0, len(name))
            if name.startswith(query_lower) or code.startswith(query_lower):
                return (1, len(name))
            return (2, len(name))
        
        return sorted(results, key=score)


# 全局实例
_supabase_searcher: Optional[SupabaseStockSearch] = None


def get_supabase_searcher() -> SupabaseStockSearch:
    """获取 Supabase 搜索器单例"""
    global _supabase_searcher
    if _supabase_searcher is None:
        _supabase_searcher = SupabaseStockSearch()
    return _supabase_searcher


def search_stock_supabase(query: str, market: str = "all", limit: int = 10) -> List[Dict[str, Any]]:
    """使用 Supabase 搜索股票"""
    return get_supabase_searcher().search(query, market, limit)
