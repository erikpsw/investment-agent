from typing import Any, Optional, List, Dict
import pandas as pd
from .yfinance_client import YFinanceClient
from .tencent_client import TencentClient
from .akshare_client import AKShareClient
from .sina_client import SinaClient
from .ashare_client import AshareQuoteClient, get_ashare_client
from .stock_search import get_stock_search, resolve_stock


class StockFetcher:
    """统一股票数据接口，自动路由到正确的数据源
    
    A股数据源优先级：
    1. Ashare (新浪+腾讯双数据源，无限流)
    2. Tencent API (备用)
    """

    def __init__(self):
        self.yfinance = YFinanceClient()
        self.tencent = TencentClient()
        self.akshare = AKShareClient()
        self.sina = SinaClient()
        self.ashare = get_ashare_client()

    @property
    def searcher(self):
        """获取共享的搜索器实例"""
        return get_stock_search()

    def resolve_input(self, user_input: str) -> Dict[str, Any]:
        """解析用户输入（名称或代码），返回股票信息
        
        Args:
            user_input: 用户输入，可以是：
                - 公司名称：茅台、苹果、腾讯
                - 股票代码：sh600519、AAPL、hk00700
                - 部分名称：贵州茅、Apple
                
        Returns:
            包含 code, name, market 的字典
        """
        result = resolve_stock(user_input)
        if result:
            return result
        return {
            "code": user_input,
            "name": "",
            "market": "UNKNOWN",
            "display": user_input,
        }

    def search(self, query: str, market: str = "all", limit: int = 10) -> List[Dict[str, Any]]:
        """搜索股票
        
        Args:
            query: 搜索关键词
            market: 市场范围 ("all", "cn", "hk", "us")
            limit: 返回数量
            
        搜索策略：
        1. 先从本地CSV搜索（快速）
        2. 如果没有结果，使用 AKShare 实时搜索（较慢但准确）
        """
        # 先用本地数据快速搜索
        results = self.searcher.search(query, market, limit)
        
        # 如果结果不够，补充 AKShare 实时数据
        if len(results) < limit:
            market_lower = market.lower()
            try:
                if market_lower in ("all", "hk"):
                    hk_results = self.akshare.search_hk_stock(query, limit - len(results))
                    # 去重
                    existing_codes = {r["code"].lower() for r in results}
                    for r in hk_results:
                        if r["code"].lower() not in existing_codes:
                            results.append(r)
                            existing_codes.add(r["code"].lower())
                
                if market_lower in ("all", "us") and len(results) < limit:
                    us_results = self.akshare.search_us_stock(query, limit - len(results))
                    existing_codes = {r["code"].lower() for r in results}
                    for r in us_results:
                        if r["code"].lower() not in existing_codes:
                            results.append(r)
                            existing_codes.add(r["code"].lower())
            except Exception:
                pass
        
        return results[:limit]

    def get_quote_by_name(self, name: str) -> Dict[str, Any]:
        """通过名称获取行情
        
        Args:
            name: 公司名称或股票代码
            
        Returns:
            行情数据，包含解析后的股票信息
        """
        resolved = self.resolve_input(name)
        ticker = resolved.get("code", name)
        
        quote = self.get_quote(ticker)
        
        if resolved.get("name") and not quote.get("name"):
            quote["name"] = resolved["name"]
        quote["_resolved"] = resolved
        
        return quote

    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """获取实时行情，自动识别市场
        
        Args:
            ticker: 股票代码
                - A股: sh600519, sz000001, 600519, 000001
                - 港股: hk00700, 00700.HK
                - 美股: AAPL, MSFT, TSLA
                
        数据源优先级：
        - A股: Ashare (新浪+腾讯) > Tencent
        - 港股: Sina > Tencent > YFinance
        - 美股: Sina > YFinance
        """
        ticker_lower = ticker.lower()
        
        if ticker_lower.startswith(("sh", "sz")):
            # A股
            try:
                return self.ashare.get_realtime_quote(ticker_lower)
            except Exception:
                return self.tencent.get_quote(ticker_lower)
        elif ticker_lower.startswith("hk") or ticker.endswith(".HK"):
            # 港股: 优先使用新浪 API
            hk_code = ticker_lower.replace(".hk", "")
            if not hk_code.startswith("hk"):
                hk_code = f"hk{hk_code}"
            
            try:
                quote = self.sina.get_hk_quote(hk_code)
                if quote.get("price") is not None:
                    return quote
            except Exception:
                pass
            
            # 备用腾讯数据源
            try:
                quote = self.tencent.get_hk_quote(hk_code)
                if "error" not in quote:
                    return quote
            except Exception:
                pass
            
            # 最后使用 yfinance
            code = hk_code.replace("hk", "").lstrip("0").zfill(4)
            return self.yfinance.get_quote(f"{code}.HK")
        elif ticker_lower.isdigit():
            # 纯数字 A股代码
            normalized = f"sh{ticker_lower}" if ticker_lower.startswith("6") else f"sz{ticker_lower}"
            try:
                return self.ashare.get_realtime_quote(normalized)
            except Exception:
                return self.tencent.get_quote(normalized)
        else:
            # 美股: 优先使用新浪 API
            try:
                quote = self.sina.get_us_quote(ticker.upper())
                if quote.get("price") is not None:
                    return quote
            except Exception:
                pass
            
            # 备用 yfinance
            return self.yfinance.get_quote(ticker.upper())

    def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """获取历史行情
        
        数据源优先级:
        - A股: Ashare (新浪+腾讯)
        - 港股: Tencent > AKShare (东方财富) > YFinance
        - 美股: Tencent > Sina > AKShare > YFinance
        """
        # 映射 period 到数据条数
        period_map = {"1y": 250, "6mo": 125, "3mo": 65, "1mo": 22, "5d": 5, "1d": 1}
        limit = period_map.get(period, 250)
        
        if self._is_china_stock(ticker):
            ticker_lower = ticker.lower()
            if not ticker_lower.startswith(("sh", "sz")):
                ticker_lower = f"sh{ticker_lower}" if ticker_lower.startswith("6") else f"sz{ticker_lower}"
            
            interval_map = {"1d": "1d", "1wk": "1w", "1mo": "1M", "5m": "5m", "15m": "15m", "60m": "60m"}
            freq = interval_map.get(interval, "1d")
            
            return self.ashare.get_price(ticker_lower, count=limit, frequency=freq)
        
        if self._is_hk_stock(ticker):
            # 港股: 优先使用腾讯 (最稳定)
            try:
                df = self.tencent.get_hk_history(ticker, limit=limit)
                if not df.empty:
                    df = self._standardize_columns(df)
                    if 'Close' in df.columns and 'Open' in df.columns:
                        return df
            except Exception as e:
                print(f"[StockFetcher] Tencent HK history failed: {e}")
            
            # 备用 AKShare
            try:
                df = self.akshare.get_hk_history(ticker)
                if not df.empty:
                    df = self._standardize_columns(df)
                    if 'Close' in df.columns and 'Open' in df.columns:
                        return df
            except Exception as e:
                print(f"[StockFetcher] AKShare HK history failed: {e}")
            
            # 最后 yfinance
            ticker_lower = ticker.lower()
            code = ticker_lower.replace("hk", "").replace(".hk", "")
            code = code.lstrip("0") or "0"
            if len(code) < 4:
                code = code.zfill(4)
            yf_ticker = f"{code}.HK"
            return self.yfinance.get_history(yf_ticker, period, interval)
        
        # 美股: 优先使用新浪 (数据更完整)
        try:
            df = self.sina.get_us_history(ticker, limit=limit)
            if not df.empty:
                df = self._standardize_columns(df)
                if 'Close' in df.columns and 'Open' in df.columns:
                    return df
        except Exception as e:
            print(f"[StockFetcher] Sina US history failed: {e}")
        
        # 备用腾讯
        try:
            df = self.tencent.get_us_history(ticker, limit=limit)
            if not df.empty and len(df) > 10:  # 腾讯数据可能不完整
                df = self._standardize_columns(df)
                if 'Close' in df.columns and 'Open' in df.columns:
                    return df
        except Exception as e:
            print(f"[StockFetcher] Tencent US history failed: {e}")
        
        # 备用 AKShare
        try:
            df = self.akshare.get_us_history(ticker)
            if not df.empty:
                df = self._standardize_columns(df)
                if 'Close' in df.columns and 'Open' in df.columns:
                    return df
        except Exception as e:
            print(f"[StockFetcher] AKShare US history failed: {e}")
        
        # 最后使用 yfinance
        return self.yfinance.get_history(ticker.upper(), period, interval)
    
    def _standardize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化列名为 yfinance 格式 (首字母大写)"""
        column_map = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'amount': 'Amount',
        }
        df = df.rename(columns={k: v for k, v in column_map.items() if k in df.columns})
        # 如果还有小写列名，首字母大写
        df.columns = [c.capitalize() if c.islower() else c for c in df.columns]
        return df

    def get_financials(self, ticker: str) -> Dict[str, pd.DataFrame]:
        """获取财务报表"""
        if self._is_china_stock(ticker):
            return self.akshare.get_financial_summary(ticker)
        return self.yfinance.get_financials(ticker.upper())

    def get_key_metrics(self, ticker: str) -> Dict[str, Any]:
        """获取关键财务指标"""
        if self._is_china_stock(ticker):
            df = self.akshare.get_financial_indicators(ticker)
            if "error" in df.columns:
                return {"error": df["error"].iloc[0]}
            return df.to_dict("records")[0] if len(df) > 0 else {}
        return self.yfinance.get_key_metrics(ticker.upper())

    def get_market_overview(self) -> Dict[str, Any]:
        """获取市场概览"""
        return self.tencent.get_market_overview()

    def _is_china_stock(self, ticker: str) -> bool:
        """判断是否为 A 股"""
        ticker_lower = ticker.lower()
        return (
            ticker_lower.startswith(("sh", "sz")) or
            ticker_lower.isdigit()
        )

    def _is_hk_stock(self, ticker: str) -> bool:
        """判断是否为港股"""
        ticker_lower = ticker.lower()
        return ticker_lower.startswith("hk") or ticker.endswith(".HK")
