import yfinance as yf
import pandas as pd
from typing import Any, Dict
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from cachetools import TTLCache
import threading
import re
import math
from numbers import Real
from investment.data.quote_timing import epoch_quote_time_fields


class RateLimitError(Exception):
    """yfinance 限流错误"""
    pass


# 缓存失败的股票，避免重复请求
_error_cache: TTLCache = TTLCache(maxsize=100, ttl=120)
_error_lock = threading.Lock()


class YFinanceClient:
    """美股数据客户端，基于 yfinance
    
    特性:
    - 自动重试：遇到限流时快速重试
    - 内存缓存：行情数据缓存 60 秒，历史数据缓存 5 分钟
    - 错误缓存：失败的请求缓存 2 分钟避免重复
    """

    @staticmethod
    def _provider_ticker(ticker: str) -> str:
        symbol = ticker.strip().upper()
        # A/B share-class separators differ from Yahoo's exchange suffixes.
        return symbol.replace(".", "-") if re.fullmatch(r"[A-Z][A-Z0-9]*\.[AB]", symbol) else symbol

    def _berkshire_pb(self, info):
        """Use aggregate common equity; Yahoo's B-share bookValue can be A-share based."""
        cap = info.get("marketCap")
        if info.get("currency") != "USD" or info.get("financialCurrency") != "USD" or isinstance(cap, bool) or not isinstance(cap, (int, float)) or not math.isfinite(cap) or cap <= 0:
            return None, None
        stock = yf.Ticker("BRK-B")
        candidates = []
        for field in ("quarterly_balance_sheet", "balance_sheet"):
            try:
                frame = getattr(stock, field)
                if "Common Stock Equity" not in frame.index:
                    continue
                for column in frame.columns:
                    day = pd.Timestamp(column).date()
                    age = (datetime.now().date() - day).days
                    if not 0 <= age <= 400:
                        continue
                    equity = frame.at["Common Stock Equity", column]
                    candidates.append((day, equity))
            except Exception:
                continue
        if candidates:
            day, equity = max(candidates, key=lambda candidate: candidate[0])
            if not isinstance(equity, bool) and isinstance(equity, Real) and math.isfinite(equity) and equity > 0:
                ratio = cap / float(equity)
                if math.isfinite(ratio):
                    return ratio, f"Yahoo Finance（总市值/普通股权益；报表{day.isoformat()}）"
        return None, None
    
    def __init__(self):
        self._quote_cache: TTLCache = TTLCache(maxsize=100, ttl=60)
        self._history_cache: TTLCache = TTLCache(maxsize=50, ttl=300)
        self._lock = threading.Lock()

    def _check_error_cache(self, ticker: str) -> bool:
        """检查是否在错误缓存中"""
        with _error_lock:
            return ticker in _error_cache
    
    def _add_to_error_cache(self, ticker: str, error: str):
        """添加到错误缓存"""
        with _error_lock:
            _error_cache[ticker] = error

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True
    )
    def _fetch_info(self, ticker: str) -> Dict[str, Any]:
        """获取股票信息，带重试逻辑"""
        try:
            symbol = self._provider_ticker(ticker)
            stock = yf.Ticker(symbol)
            info = stock.info
            if info and info.get("symbol") and str(info["symbol"]).upper() != symbol:
                raise ValueError("Yahoo response symbol does not match requested security")
            if not info or info.get("trailingPegRatio") is None and info.get("currentPrice") is None:
                if "Too Many Requests" in str(info) or not info:
                    raise RateLimitError(f"Rate limited for {ticker}")
            return info
        except Exception as e:
            if "Too Many Requests" in str(e) or "429" in str(e):
                raise RateLimitError(f"Rate limited: {e}")
            raise

    def get_quote(self, ticker: str) -> Dict[str, Any]:
        """获取实时行情（带缓存）"""
        cache_key = f"quote:{ticker}"
        
        with self._lock:
            if cache_key in self._quote_cache:
                return self._quote_cache[cache_key]
        
        # 检查错误缓存
        if self._check_error_cache(ticker):
            return {
                "ticker": ticker,
                "name": ticker,
                "error": "Temporarily unavailable (cached error)",
                "timestamp": datetime.now().isoformat(),
                "market": "US",
            }
        
        try:
            info = self._fetch_info(ticker)
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            quote_time = epoch_quote_time_fields(info.get("regularMarketTime") if info.get("regularMarketPrice") is not None and price == info.get("regularMarketPrice") else None)
            
            result = {
                "ticker": ticker,
                "name": info.get("shortName", info.get("longName", ticker)),
                "price": price,
                "change": info.get("regularMarketChange"),
                "change_percent": info.get("regularMarketChangePercent"),
                "volume": info.get("regularMarketVolume"),
                "market_cap": info.get("marketCap"),
                "pe_ratio": info.get("trailingPE"),
                "source": "Yahoo Finance",
                "pe_source": "Yahoo Finance",
                "pe_basis": "TTM",
                "eps": info.get("trailingEps"),
                "dividend_yield": info.get("dividendYield"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
                **quote_time,
                "market": "US",
            }
            
            with self._lock:
                self._quote_cache[cache_key] = result
            
            return result
        except Exception as e:
            self._add_to_error_cache(ticker, str(e))
            return {
                "ticker": ticker,
                "name": ticker,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "market": "US",
            }

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        reraise=True
    )
    def get_history(
        self,
        ticker: str,
        period: str = "1y",
        interval: str = "1d"
    ) -> pd.DataFrame:
        """获取历史行情（带缓存和重试）
        
        Args:
            ticker: 股票代码
            period: 时间段 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            interval: K线周期 (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
        """
        cache_key = f"history:{ticker}:{period}:{interval}"
        
        with self._lock:
            if cache_key in self._history_cache:
                return self._history_cache[cache_key]
        
        # 检查错误缓存
        if self._check_error_cache(ticker):
            return pd.DataFrame()
        
        try:
            stock = yf.Ticker(self._provider_ticker(ticker))
            df = stock.history(period=period, interval=interval)
            
            if df.empty:
                self._add_to_error_cache(ticker, "Empty data")
                return df
            
            with self._lock:
                self._history_cache[cache_key] = df
            
            return df
        except Exception as e:
            self._add_to_error_cache(ticker, str(e))
            return pd.DataFrame()

    def get_financials(self, ticker: str) -> Dict[str, pd.DataFrame]:
        """获取财务报表"""
        if self._check_error_cache(ticker):
            return {}
        
        try:
            stock = yf.Ticker(self._provider_ticker(ticker))
            return {
                "income_statement": stock.financials,
                "balance_sheet": stock.balance_sheet,
                "cash_flow": stock.cashflow,
                "quarterly_income": stock.quarterly_financials,
                "quarterly_balance": stock.quarterly_balance_sheet,
                "quarterly_cashflow": stock.quarterly_cashflow,
            }
        except Exception as e:
            self._add_to_error_cache(ticker, str(e))
            return {}

    def get_key_metrics(self, ticker: str) -> Dict[str, Any]:
        """获取关键财务指标（使用缓存的 info）"""
        try:
            info = self._fetch_info(ticker)
            pb_ratio, pb_source = info.get("priceToBook"), "Yahoo Finance"
            if self._provider_ticker(ticker) == "BRK-B":
                pb_ratio, pb_source = self._berkshire_pb(info)
            
            return {
                "ticker": ticker,
                "name": info.get("shortName") or info.get("longName"),
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": pb_ratio,
                "pb_source": pb_source,
                "eps": info.get("trailingEps"),
                "source": "Yahoo Finance",
                "pe_source": "Yahoo Finance",
                "pe_basis": "TTM",
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
        except Exception as e:
            return {"ticker": ticker, "error": str(e)}

    def get_earnings(self, ticker: str) -> Dict[str, pd.DataFrame]:
        """获取收益数据"""
        stock = yf.Ticker(self._provider_ticker(ticker))
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
