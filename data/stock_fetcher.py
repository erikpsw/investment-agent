from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, List, Dict
from datetime import datetime
import pandas as pd
from .yfinance_client import YFinanceClient
from .tencent_client import TencentClient
from .akshare_client import AKShareClient
from .sina_client import SinaClient
from .ashare_client import AshareQuoteClient, get_ashare_client
from .stock_search import get_stock_search, resolve_stock


A_SHARE_INDICES = (
    ("sh000001", "上证指数", "000001.SS"),
    ("sz399001", "深证成指", "399001.SZ"),
    ("sz399006", "创业板指", "399006.SZ"),
    ("sh000300", "沪深300", "000300.SS"),
)

GLOBAL_INDICES = (
    ("^HSI", "恒生指数", "HK"),
    ("HSTECH.HK", "恒生科技指数", "HK"),
    ("^GSPC", "标普500", "US"),
    ("^IXIC", "纳斯达克综合", "US"),
    ("^DJI", "道琼斯工业指数", "US"),
)


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

        normalized_query = query.strip()
        if normalized_query.isdigit() and len(normalized_query) == 6:
            resolved = self.searcher.resolve(normalized_query)
            exact_code = str((resolved or {}).get("code") or "")
            if exact_code and not any(str(item.get("code")) == exact_code for item in results):
                try:
                    quote = self.get_quote(exact_code)
                    if quote.get("price") is not None and not quote.get("error"):
                        resolved = {
                            **resolved,
                            "name": quote.get("name") or resolved.get("name") or exact_code,
                            "display": f"{quote.get('name') or exact_code} ({exact_code})",
                        }
                        results.insert(0, resolved)
                except Exception:
                    pass
        
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
        elif self._is_hk_stock(ticker):
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

    def get_quotes(self, items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Fetch a watchlist's quotes efficiently, using Sina's A-share batch API."""
        results: Dict[str, Dict[str, Any]] = {}
        cn_items = [item for item in items if str(item.get("market") or "").upper() == "CN"]
        if cn_items:
            try:
                quotes = self.ashare.get_realtime_quotes([
                    str(item.get("ticker") or "") for item in cn_items
                ])
                for item, quote in zip(cn_items, quotes):
                    results[str(item.get("ticker") or "")] = quote
            except Exception:
                # Keep the rest of the batch useful even when one provider is down.
                pass

        remaining = [item for item in items if str(item.get("ticker") or "") not in results]
        if remaining:
            def load(item: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
                ticker = str(item.get("ticker") or "")
                return ticker, self.get_quote(ticker)

            with ThreadPoolExecutor(max_workers=min(6, len(remaining))) as executor:
                results.update(executor.map(load, remaining))
        return results

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
        period_map = {"2y": 500, "5y": 1260, "10y": 2520, "max": 20000, "1y": 250, "6mo": 125, "3mo": 65, "1mo": 22, "5d": 5, "1d": 1}
        limit = period_map.get(period, 250)
        
        # Long ranges need providers that are not capped at a few hundred bars.
        if period in {"5y", "10y", "max"}:
            if self._is_china_stock(ticker):
                code = ticker.lower().removeprefix("sh").removeprefix("sz").removeprefix("bj")
                exchange = "SS" if ticker.lower().startswith("sh") or code.startswith(("5", "6", "9")) else "BJ" if ticker.lower().startswith("bj") else "SZ"
                yf_ticker = f"{code}.{exchange}"
            elif self._is_hk_stock(ticker):
                code = ticker.lower().replace("hk", "").replace(".hk", "").lstrip("0").zfill(4)
                yf_ticker = f"{code}.HK"
            else:
                yf_ticker = ticker.upper()
            try:
                df = self.yfinance.get_history(yf_ticker, period, interval)
                if df is not None and not df.empty:
                    return self._standardize_columns(df)
            except Exception as exc:
                print(f"[StockFetcher] Long history provider failed: {exc}")
            # Explicit dates prevent AKShare silently falling back to one year.
            from datetime import datetime, timedelta
            end = datetime.now()
            start = "19900101" if period == "max" else (end - timedelta(days={"2y": 731, "5y": 1827, "10y": 3653}[period])).strftime("%Y%m%d")
            if self._is_hk_stock(ticker):
                return self._standardize_columns(self.akshare.get_hk_history(ticker, start_date=start, end_date=end.strftime("%Y%m%d")))
            if not self._is_china_stock(ticker):
                return self._standardize_columns(self.akshare.get_us_history(ticker, start_date=start, end_date=end.strftime("%Y%m%d")))
            import akshare as ak
            if code.startswith(("5", "15", "16", "18")):
                df = ak.fund_etf_hist_em(symbol=code, start_date=start, end_date=end.strftime("%Y%m%d"), adjust="qfq")
            else:
                df = ak.stock_zh_a_hist(symbol=code, start_date=start, end_date=end.strftime("%Y%m%d"), adjust="qfq")
            if df is not None and not df.empty:
                df = df.rename(columns={"日期": "Date", "开盘": "Open", "收盘": "Close", "最高": "High", "最低": "Low", "成交量": "Volume"})
                df.index = pd.to_datetime(df.pop("Date"))
            return df

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
        
        # 港股需要转换为 yfinance 格式
        if self._is_hk_stock(ticker):
            code = ticker.lower().replace("hk", "").replace(".hk", "")
            code = code.lstrip("0") or "0"
            if len(code) < 4:
                code = code.zfill(4)
            yf_ticker = f"{code}.HK"
            return self.yfinance.get_key_metrics(yf_ticker)
        
        return self.yfinance.get_key_metrics(ticker.upper())

    def get_market_overview(self) -> Dict[str, Any]:
        """获取 A 股、港股和美股主要指数，单个行情失败不影响其他指数。"""
        indices: List[Dict[str, Any]] = []

        for code, name, history_ticker in A_SHARE_INDICES:
            try:
                quote = self.tencent.get_index(code, name)
                if quote.get("price") is None or quote.get("error"):
                    continue
                indices.append({
                    "code": code,
                    "name": name,
                    "market": "CN",
                    "history_ticker": history_ticker,
                    "price": quote.get("price"),
                    "change": quote.get("change"),
                    "change_percent": quote.get("change_percent"),
                })
            except Exception:
                continue

        for ticker, name, market in GLOBAL_INDICES:
            try:
                quote = self.yfinance.get_quote(ticker)
                if quote.get("price") is None or quote.get("error"):
                    continue
                indices.append({
                    "code": ticker,
                    "name": name,
                    "market": market,
                    "history_ticker": ticker,
                    "price": quote.get("price"),
                    "change": quote.get("change"),
                    "change_percent": quote.get("change_percent"),
                })
            except Exception:
                continue

        return {
            "timestamp": datetime.now().isoformat(),
            "indices": indices,
        }

    def _is_china_stock(self, ticker: str) -> bool:
        """判断是否为 A 股"""
        ticker_lower = ticker.lower()
        return (
            ticker_lower.startswith(("sh", "sz")) or
            (ticker_lower.isdigit() and len(ticker_lower) == 6)
        )

    def _is_hk_stock(self, ticker: str) -> bool:
        """判断是否为港股"""
        ticker_lower = ticker.lower()
        return ticker_lower.startswith("hk") or ticker_lower.endswith(".hk") or (ticker_lower.isdigit() and len(ticker_lower) in (4, 5))
