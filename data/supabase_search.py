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
            # 优先使用 service key（绕过 RLS），否则使用 anon key
            key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
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
        """搜索股票 - 优先使用 Supabase，失败则回退到本地，港股/美股额外使用别名和 yfinance"""
        results = []
        existing_codes = set()
        
        # 先检查港股别名（快速匹配）
        if market in ("all", "hk", "HK"):
            hk_code = self.HK_ALIASES.get(query)
            if hk_code:
                results.append({
                    "code": f"hk{hk_code}",
                    "name": query,
                    "market": "HK",
                    "display": f"{query} (hk{hk_code})",
                    "exchange": "HKEX",
                })
                existing_codes.add(f"hk{hk_code}".lower())
        
        if not self.client:
            fallback_results = self.fallback.search(query, market, limit - len(results))
            for r in fallback_results:
                if r.get("code", "").lower() not in existing_codes:
                    results.append(r)
                    existing_codes.add(r.get("code", "").lower())
            return results[:limit]
        
        try:
            supabase_results = self._search_supabase(query, market, limit)
            for r in supabase_results:
                if r.get("code", "").lower() not in existing_codes:
                    results.append(r)
                    existing_codes.add(r.get("code", "").lower())
            
            # 如果搜索美股且结果不足，尝试使用 yfinance 补充
            if market in ("all", "us", "US") and len(results) < limit:
                yf_results = self._search_yfinance(query, limit - len(results))
                for r in yf_results:
                    if r.get("code", "").lower() not in existing_codes:
                        results.append(r)
                        existing_codes.add(r.get("code", "").lower())
            
            return results[:limit]
        except Exception as e:
            print(f"[SupabaseSearch] Search error: {e}, falling back to local")
            fallback_results = self.fallback.search(query, market, limit - len(results))
            for r in fallback_results:
                if r.get("code", "").lower() not in existing_codes:
                    results.append(r)
                    existing_codes.add(r.get("code", "").lower())
            return results[:limit]
    
    def _search_yfinance(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """使用 yfinance 搜索美股"""
        try:
            import yfinance as yf
            
            # 检查别名
            search_term = self.ALIASES.get(query, query).upper()
            
            # 尝试直接获取股票信息
            ticker = yf.Ticker(search_term)
            info = ticker.info
            
            if info and info.get("symbol"):
                return [{
                    "code": info.get("symbol", search_term),
                    "name": info.get("shortName") or info.get("longName") or search_term,
                    "market": "US",
                    "display": f"{info.get('shortName', search_term)} ({info.get('symbol', search_term)})",
                    "exchange": info.get("exchange", ""),
                }]
        except Exception as e:
            print(f"[SupabaseSearch] yfinance search failed: {e}")
        
        return []
    
    # 中文别名映射（用于搜索港股/美股）
    # 港股代码映射 (中文名 -> 港股代码)
    HK_ALIASES = {
        "腾讯": "00700", "腾讯控股": "00700",
        "阿里": "09988", "阿里巴巴": "09988", "阿里健康": "00241",
        "美团": "03690", "美团点评": "03690",
        "京东": "09618", "京东健康": "06618", "京东物流": "02618",
        "小米": "01810", "小米集团": "01810",
        "百度": "09888",
        "网易": "09999",
        "快手": "01024", "快手科技": "01024",
        "哔哩哔哩": "09626", "B站": "09626",
        "商汤": "00020", "商汤科技": "00020",
        "华为": None,  # 未上市
        "比亚迪": "01211", "比亚迪电子": "00285",
        "中芯国际": "00981",
        "联想": "00992", "联想集团": "00992",
        "中国移动": "00941", "中移动": "00941",
        "中国电信": "00728", "中国联通": "00762",
        "中国平安": "02318", "平安保险": "02318",
        "招商银行": "03968", "工商银行": "01398", "建设银行": "00939",
        "农业银行": "01288", "中国银行": "03988", "交通银行": "03328",
        "汇丰": "00005", "汇丰控股": "00005", "恒生银行": "00011",
        "友邦": "01299", "友邦保险": "01299",
        "港交所": "00388", "香港交易所": "00388",
        "长和": "00001", "长江实业": "01113",
        "新鸿基": "00016", "新世界": "00017", "恒隆": "00010",
        "永辉": "09995", "永辉超市": "09995",
        "海底捞": "06862", "海尔": "06690", "海尔智家": "06690",
        "吉利": "00175", "吉利汽车": "00175",
        "理想汽车": "02015", "蔚来": "09866", "小鹏": "09868",
        "携程": "09961", "同程": "00780",
        "中石油": "00857", "中石化": "00386", "中海油": "00883",
        "中国神华": "01088", "中煤能源": "01898",
        "药明康德": "02359", "药明生物": "02269",
        "万科": "02202", "碧桂园": "02007", "恒大": "03333",
        "融创": "01918", "龙湖": "00960",
    }
    
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
        "禾赛": "HSAI",
        "禾赛科技": "HSAI",
        "甲骨文": "ORCL",
        "超微": "AMD",
        "台积电": "TSM",
        "博通": "AVGO",
        "思科": "CSCO",
        "赛灵思": "XLNX",
        "应用材料": "AMAT",
        "德州仪器": "TXN",
        "万豪": "MAR",
        "星巴克": "SBUX",
        "可口可乐": "KO",
        "百事": "PEP",
        "麦当劳": "MCD",
        "沃尔玛": "WMT",
        "迪士尼": "DIS",
        "耐克": "NKE",
        "宝洁": "PG",
        "强生": "JNJ",
        "辉瑞": "PFE",
        "默克": "MRK",
        "摩根大通": "JPM",
        "高盛": "GS",
        "美国银行": "BAC",
        "花旗": "C",
        "伯克希尔": "BRK",
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
