import yfinance as yf
import pandas as pd
from typing import Any
from datetime import datetime, timedelta


class YFinanceClient:
    """美股数据客户端，基于 yfinance"""

    def get_quote(self, ticker: str) -> dict[str, Any]:
        """获取实时行情"""
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker,
            "name": info.get("shortName", info.get("longName", ticker)),
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "change": info.get("regularMarketChange"),
            "change_percent": info.get("regularMarketChangePercent"),
            "volume": info.get("regularMarketVolume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "eps": info.get("trailingEps"),
            "dividend_yield": info.get("dividendYield"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
            "timestamp": datetime.now().isoformat(),
        }

    def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """获取历史行情
        
        Args:
            ticker: 股票代码
            period: 时间段 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: K线周期 (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        """
        stock = yf.Ticker(ticker)
        return stock.history(period=period, interval=interval)

    def get_financials(self, ticker: str) -> dict[str, pd.DataFrame]:
        """获取财务报表"""
        stock = yf.Ticker(ticker)
        return {
            "income_statement": stock.financials,
            "balance_sheet": stock.balance_sheet,
            "cash_flow": stock.cashflow,
            "quarterly_income": stock.quarterly_financials,
            "quarterly_balance": stock.quarterly_balance_sheet,
            "quarterly_cashflow": stock.quarterly_cashflow,
        }

    def get_key_metrics(self, ticker: str) -> dict[str, Any]:
        """获取关键财务指标"""
        stock = yf.Ticker(ticker)
        info = stock.info

        return {
            "ticker": ticker,
            "revenue": info.get("totalRevenue"),
            "gross_profit": info.get("grossProfits"),
            "operating_income": info.get("operatingIncome"),
            "net_income": info.get("netIncomeToCommon"),
            "total_assets": info.get("totalAssets"),
            "total_debt": info.get("totalDebt"),
            "total_equity": info.get("totalStockholderEquity"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "profit_margin": info.get("profitMargins"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
        }

    def get_earnings(self, ticker: str) -> dict[str, pd.DataFrame]:
        """获取收益数据"""
        stock = yf.Ticker(ticker)
        return {
            "earnings": stock.earnings,
            "quarterly_earnings": stock.quarterly_earnings,
            "earnings_dates": stock.earnings_dates,
        }

    def search(self, query: str) -> list[dict]:
        """搜索股票"""
        try:
            results = yf.Tickers(query)
            return [{"ticker": t, "name": t} for t in results.tickers.keys()]
        except Exception:
            return []
