"""
股票搜索模块 - 基于本地CSV数据，支持 A股/港股/美股 名称搜索
数据来源: https://github.com/irachex/open-stock-data
"""
import pandas as pd
from typing import Any, Optional, List, Dict, Tuple
from pathlib import Path
import threading


_search_instance: Optional["StockSearch"] = None
_search_lock = threading.Lock()


def get_stock_search() -> "StockSearch":
    """获取全局共享的 StockSearch 实例"""
    global _search_instance
    if _search_instance is None:
        with _search_lock:
            if _search_instance is None:
                _search_instance = StockSearch()
    return _search_instance


class StockSearch:
    """股票搜索器，基于本地CSV数据，无API调用无限流"""
    
    def __init__(self):
        self._data_dir = Path(__file__).parent / "stock_lists"
        self._stocks: Optional[pd.DataFrame] = None
        self._loaded = False
    
    def _load_data(self):
        """加载本地股票列表数据"""
        if self._loaded:
            return
        
        dfs = []
        
        sse_path = self._data_dir / "SSE.csv"
        if sse_path.exists():
            df = pd.read_csv(sse_path)
            df["market"] = "CN"
            df["ticker"] = "sh" + df["code"].astype(str).str.zfill(6)
            dfs.append(df)
        
        szse_path = self._data_dir / "SZSE.csv"
        if szse_path.exists():
            df = pd.read_csv(szse_path)
            df["market"] = "CN"
            df["ticker"] = "sz" + df["code"].astype(str).str.zfill(6)
            dfs.append(df)
        
        hkex_path = self._data_dir / "HKEX.csv"
        if hkex_path.exists():
            df = pd.read_csv(hkex_path)
            df["market"] = "HK"
            df["ticker"] = "hk" + df["code"].astype(str).str.zfill(5)
            dfs.append(df)
        
        nasdaq_path = self._data_dir / "NASDAQ.csv"
        if nasdaq_path.exists():
            df = pd.read_csv(nasdaq_path)
            df["market"] = "US"
            df["ticker"] = df["code"].astype(str).str.upper()
            dfs.append(df)
        
        nyse_path = self._data_dir / "NYSE.csv"
        if nyse_path.exists():
            df = pd.read_csv(nyse_path)
            df["market"] = "US"
            df["ticker"] = df["code"].astype(str).str.upper()
            dfs.append(df)
        
        if dfs:
            self._stocks = pd.concat(dfs, ignore_index=True)
            self._stocks["name_lower"] = self._stocks["name"].str.lower()
            self._stocks["code_str"] = self._stocks["code"].astype(str)
            
            try:
                from pypinyin import pinyin, Style
                def get_pinyin(name):
                    try:
                        if any('\u4e00' <= c <= '\u9fff' for c in str(name)):
                            py = pinyin(str(name), style=Style.FIRST_LETTER)
                            return "".join([p[0] for p in py]).lower()
                    except:
                        pass
                    return ""
                self._stocks["pinyin"] = self._stocks["name"].apply(get_pinyin)
            except ImportError:
                self._stocks["pinyin"] = ""
        else:
            self._stocks = pd.DataFrame(columns=["code", "name", "market", "ticker", "name_lower", "code_str", "pinyin"])
        
        self._loaded = True
    
    def search(self, query: str, market: str = "all", limit: int = 10) -> List[Dict[str, Any]]:
        """搜索股票
        
        Args:
            query: 搜索关键词（公司名称、代码、拼音首字母）
            market: 市场范围 ("all", "cn", "hk", "us")
            limit: 返回结果数量限制
            
        Returns:
            搜索结果列表，每项包含 code, name, market, display
        """
        self._load_data()
        
        query = query.strip()
        if not query or self._stocks is None or self._stocks.empty:
            return []
        
        # 检查是否有别名映射
        alias = self._check_alias(query)
        search_terms = [query.lower()]
        if alias:
            search_terms.append(alias.lower())
        
        df = self._stocks
        if market != "all":
            market_upper = market.upper()
            df = df[df["market"] == market_upper]
        
        # 搜索所有相关词
        mask = pd.Series([False] * len(df), index=df.index)
        for term in search_terms:
            mask = mask | (
                df["name_lower"].str.contains(term, case=False, na=False, regex=False) |
                df["code_str"].str.contains(term, case=False, na=False, regex=False) |
                df["ticker"].str.contains(term, case=False, na=False, regex=False)
            )
        
        if "pinyin" in df.columns:
            for term in search_terms:
                mask = mask | df["pinyin"].str.contains(term, case=False, na=False, regex=False)
        
        matches = df[mask]
        
        results = []
        for _, row in matches.iterrows():
            results.append({
                "code": row["ticker"],
                "name": row["name"],
                "market": row["market"],
                "display": f"{row['name']} ({row['ticker']})",
                "exchange": row.get("exchange", ""),
            })
        
        results = self._rank_results(results, query)
        
        return results[:limit]
    
    def resolve(self, query: str) -> Optional[Dict[str, Any]]:
        """解析用户输入，返回最匹配的股票
        
        Args:
            query: 用户输入（可能是名称、代码、或混合）
            
        Returns:
            最匹配的股票信息，包含 code, name, market
        """
        query = query.strip()
        
        if not query:
            return None
        
        if self._looks_like_code(query):
            return self._resolve_code(query)
        
        alias = self._check_alias(query)
        if alias:
            results = self.search(alias, limit=1)
            if results:
                return results[0]
        
        results = self.search(query, limit=1)
        if results:
            return results[0]
        
        return None
    
    def _check_alias(self, query: str) -> Optional[str]:
        """检查常用别名映射（中文 -> 英文公司名/代码）"""
        aliases = {
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
            "理想": "LI AUTO",
            "小鹏": "XPENG",
            "哔哩哔哩": "BILIBILI",
            "B站": "BILIBILI",
            "苹果": "AAPL",
            "谷歌": "GOOG",
            "微软": "MSFT",
            "亚马逊": "AMZN",
            "特斯拉": "TSLA",
            "英伟达": "NVDA",
            "脸书": "META",
            "Meta": "META",
            "奈飞": "NFLX",
            "英特尔": "INTC",
            "高通": "QCOM",
            "星巴克": "SBUX",
            "可口可乐": "KO",
            "耐克": "NKE",
            "迪士尼": "DIS",
            "汇丰": "HSBC",
            "友邦": "AIA",
            "港交所": "HKEX",
            "长和": "CKH",
            "中移动": "CHINA MOBILE",
            "中国移动": "CHINA MOBILE",
        }
        return aliases.get(query)
    
    def _looks_like_code(self, query: str) -> bool:
        """判断输入是否像股票代码"""
        query = query.strip()
        
        if any('\u4e00' <= c <= '\u9fff' for c in query):
            return False
        
        query_upper = query.upper()
        
        if query.isdigit() and len(query) in (5, 6):
            return True
        
        if query_upper.startswith(("SH", "SZ", "HK")) and query_upper[2:].isdigit():
            return True
        
        if query.isascii() and query.isalpha() and 1 <= len(query) <= 5:
            return True
        
        if query_upper.endswith((".HK", ".SS", ".SZ")):
            return True
        
        return False
    
    def _resolve_code(self, code: str) -> Dict[str, Any]:
        """解析股票代码"""
        code = code.strip()
        code_upper = code.upper()
        code_lower = code.lower()
        
        if code_lower.startswith("sh"):
            return {
                "code": code_lower,
                "name": "",
                "market": "CN",
                "display": code_lower,
            }
        elif code_lower.startswith("sz"):
            return {
                "code": code_lower,
                "name": "",
                "market": "CN",
                "display": code_lower,
            }
        elif code_lower.startswith("hk"):
            return {
                "code": code_lower,
                "name": "",
                "market": "HK",
                "display": code_lower,
            }
        elif code.isdigit():
            if len(code) == 5:
                ticker = f"hk{code.zfill(5)}"
                return {
                    "code": ticker,
                    "name": "",
                    "market": "HK",
                    "display": ticker,
                }
            elif code.startswith("6"):
                ticker = f"sh{code.zfill(6)}"
            else:
                ticker = f"sz{code.zfill(6)}"
            return {
                "code": ticker,
                "name": "",
                "market": "CN",
                "display": ticker,
            }
        elif code_upper.isalpha():
            return {
                "code": code_upper,
                "name": "",
                "market": "US",
                "display": code_upper,
            }
        
        return {
            "code": code,
            "name": "",
            "market": "UNKNOWN",
            "display": code,
        }
    
    def _rank_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """对搜索结果排序"""
        query_lower = query.lower()
        
        def score(item: Dict[str, Any]) -> Tuple[int, int]:
            name = item.get("name", "").lower()
            code = item.get("code", "").lower()
            
            if name == query_lower or code == query_lower:
                return (0, 0)
            
            if name.startswith(query_lower) or code.startswith(query_lower):
                return (1, len(name))
            
            if query_lower in name or query_lower in code:
                return (2, len(name))
            
            return (3, len(name))
        
        return sorted(results, key=score)


_default_searcher: Optional[StockSearch] = None


def get_stock_searcher() -> StockSearch:
    """获取默认搜索器（单例）"""
    global _default_searcher
    if _default_searcher is None:
        _default_searcher = StockSearch()
    return _default_searcher


def search_stock(query: str, market: str = "all", limit: int = 10) -> List[Dict[str, Any]]:
    """搜索股票的便捷函数"""
    return get_stock_searcher().search(query, market, limit)


def resolve_stock(query: str) -> Optional[Dict[str, Any]]:
    """解析股票输入的便捷函数"""
    return get_stock_searcher().resolve(query)
