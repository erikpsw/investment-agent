from typing import Any
import pandas as pd
from .yfinance_client import YFinanceClient
from .tencent_client import TencentClient
from .akshare_client import AKShareClient


class StockFetcher:
    """统一股票数据接口，自动路由到正确的数据源"""

    def __init__(self):
        self.yfinance = YFinanceClient()
        self.tencent = TencentClient()
        self.akshare = AKShareClient()

    def get_quote(self, ticker: str) -> dict[str, Any]:
        """获取实时行情，自动识别市场
        
        Args:
            ticker: 股票代码
                - A股: sh600519, sz000001, 600519, 000001
                - 港股: hk00700, 00700.HK
                - 美股: AAPL, MSFT, TSLA
        """
        ticker_lower = ticker.lower()
        
        if ticker_lower.startswith(("sh", "sz")):
            return self.tencent.get_quote(ticker_lower)
        elif ticker_lower.startswith("hk") or ticker.endswith(".HK"):
            hk_code = ticker_lower.replace(".hk", "")
            if not hk_code.startswith("hk"):
                hk_code = f"hk{hk_code}"
            return self.tencent.get_hk_quote(hk_code)
        elif ticker_lower.isdigit():
            if ticker_lower.startswith("6"):
                return self.tencent.get_quote(f"sh{ticker_lower}")
            else:
                return self.tencent.get_quote(f"sz{ticker_lower}")
        else:
            return self.yfinance.get_quote(ticker.upper())

    def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """获取历史行情"""
        if self._is_china_stock(ticker):
            raise NotImplementedError("A股历史数据暂未实现")
        return self.yfinance.get_history(ticker.upper(), period, interval)

    def get_financials(self, ticker: str) -> dict[str, pd.DataFrame]:
        """获取财务报表"""
        if self._is_china_stock(ticker):
            return self.akshare.get_financial_summary(ticker)
        return self.yfinance.get_financials(ticker.upper())

    def get_key_metrics(self, ticker: str) -> dict[str, Any]:
        """获取关键财务指标"""
        if self._is_china_stock(ticker):
            df = self.akshare.get_financial_indicators(ticker)
            if "error" in df.columns:
                return {"error": df["error"].iloc[0]}
            return df.to_dict("records")[0] if len(df) > 0 else {}
        return self.yfinance.get_key_metrics(ticker.upper())

    def get_market_overview(self) -> dict[str, Any]:
        """获取市场概览"""
        return self.tencent.get_market_overview()

    def search(self, query: str) -> pd.DataFrame:
        """搜索股票"""
        if any(c.isdigit() for c in query) or any("\u4e00" <= c <= "\u9fff" for c in query):
            return self.akshare.search_stock(query)
        return pd.DataFrame(self.yfinance.search(query))

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
