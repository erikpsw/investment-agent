import akshare as ak
import pandas as pd
from typing import Any, Dict, Optional, List
from datetime import datetime
from functools import lru_cache
import threading


class AKShareClient:
    """A股/港股/美股数据客户端，基于 AKShare"""
    
    def __init__(self):
        self._hk_cache: Optional[pd.DataFrame] = None
        self._us_cache: Optional[pd.DataFrame] = None
        self._cache_lock = threading.Lock()
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 60  # Cache TTL in seconds
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is still valid"""
        if cache_key not in self._cache_time:
            return False
        elapsed = (datetime.now() - self._cache_time[cache_key]).total_seconds()
        return elapsed < self._cache_ttl
    
    def get_hk_spot(self) -> pd.DataFrame:
        """获取港股实时行情列表（东方财富数据源）"""
        with self._cache_lock:
            if self._hk_cache is not None and self._is_cache_valid("hk"):
                return self._hk_cache
        
        try:
            df = ak.stock_hk_spot_em()
            with self._cache_lock:
                self._hk_cache = df
                self._cache_time["hk"] = datetime.now()
            return df
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})
    
    def get_hk_quote(self, ticker: str) -> Dict[str, Any]:
        """获取单只港股实时行情
        
        Args:
            ticker: 港股代码，如 hk00700 或 00700
        """
        code = ticker.lower().replace("hk", "").replace(".hk", "").lstrip("0") or "0"
        
        try:
            df = self.get_hk_spot()
            if "error" in df.columns:
                return {"ticker": ticker, "error": df["error"].iloc[0]}
            
            # 尝试匹配代码
            mask = df["代码"].astype(str).str.contains(code, regex=False)
            if mask.any():
                row = df[mask].iloc[0]
                return {
                    "ticker": ticker,
                    "name": row.get("名称", ""),
                    "price": self._safe_float(row.get("最新价")),
                    "change": self._safe_float(row.get("涨跌额")),
                    "change_percent": self._safe_float(row.get("涨跌幅")),
                    "prev_close": self._safe_float(row.get("昨收")),
                    "open": self._safe_float(row.get("今开")),
                    "high": self._safe_float(row.get("最高")),
                    "low": self._safe_float(row.get("最低")),
                    "volume": self._safe_float(row.get("成交量")),
                    "amount": self._safe_float(row.get("成交额")),
                    "pe_ratio": self._safe_float(row.get("市盈率-动态")),
                    "market_cap": self._safe_float(row.get("总市值")),
                    "timestamp": datetime.now().isoformat(),
                }
            
            return {"ticker": ticker, "error": "股票未找到", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"ticker": ticker, "error": str(e), "timestamp": datetime.now().isoformat()}
    
    def get_us_spot(self) -> pd.DataFrame:
        """获取美股实时行情列表（东方财富数据源）"""
        with self._cache_lock:
            if self._us_cache is not None and self._is_cache_valid("us"):
                return self._us_cache
        
        try:
            df = ak.stock_us_spot_em()
            with self._cache_lock:
                self._us_cache = df
                self._cache_time["us"] = datetime.now()
            return df
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})
    
    def get_us_quote(self, ticker: str) -> Dict[str, Any]:
        """获取单只美股实时行情
        
        Args:
            ticker: 美股代码，如 AAPL、MSFT
        """
        code = ticker.upper()
        
        try:
            df = self.get_us_spot()
            if "error" in df.columns:
                return {"ticker": ticker, "error": df["error"].iloc[0]}
            
            # 尝试匹配代码 (美股代码可能带后缀如 .O 或 .N)
            mask = df["代码"].astype(str).str.upper().str.startswith(code)
            if not mask.any():
                # 尝试精确匹配
                mask = df["代码"].astype(str).str.upper() == code
            if not mask.any():
                # 尝试包含匹配
                mask = df["代码"].astype(str).str.upper().str.contains(f"^{code}\\.", regex=True)
            
            if mask.any():
                row = df[mask].iloc[0]
                return {
                    "ticker": ticker,
                    "name": row.get("名称", ""),
                    "price": self._safe_float(row.get("最新价")),
                    "change": self._safe_float(row.get("涨跌额")),
                    "change_percent": self._safe_float(row.get("涨跌幅")),
                    "prev_close": self._safe_float(row.get("昨收")),
                    "open": self._safe_float(row.get("今开")),
                    "high": self._safe_float(row.get("最高")),
                    "low": self._safe_float(row.get("最低")),
                    "volume": self._safe_float(row.get("成交量")),
                    "amount": self._safe_float(row.get("成交额")),
                    "pe_ratio": self._safe_float(row.get("市盈率")),
                    "market_cap": self._safe_float(row.get("总市值")),
                    "timestamp": datetime.now().isoformat(),
                }
            
            return {"ticker": ticker, "error": "股票未找到", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"ticker": ticker, "error": str(e), "timestamp": datetime.now().isoformat()}
    
    def search_hk_stock(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索港股"""
        try:
            df = self.get_hk_spot()
            if "error" in df.columns:
                return []
            
            keyword_lower = keyword.lower()
            mask = (
                df["名称"].astype(str).str.lower().str.contains(keyword_lower, na=False) |
                df["代码"].astype(str).str.contains(keyword, na=False)
            )
            
            results = []
            for _, row in df[mask].head(limit).iterrows():
                code = str(row.get("代码", ""))
                results.append({
                    "code": f"hk{code.zfill(5)}",
                    "name": row.get("名称", ""),
                    "market": "HK",
                    "display": f"{row.get('名称', '')} (hk{code.zfill(5)})",
                })
            return results
        except Exception:
            return []
    
    def search_us_stock(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索美股"""
        try:
            df = self.get_us_spot()
            if "error" in df.columns:
                return []
            
            keyword_upper = keyword.upper()
            keyword_lower = keyword.lower()
            mask = (
                df["名称"].astype(str).str.lower().str.contains(keyword_lower, na=False) |
                df["代码"].astype(str).str.upper().str.contains(keyword_upper, na=False)
            )
            
            results = []
            for _, row in df[mask].head(limit).iterrows():
                code = str(row.get("代码", "")).split(".")[0]  # Remove .O, .N suffix
                results.append({
                    "code": code.upper(),
                    "name": row.get("名称", ""),
                    "market": "US",
                    "display": f"{row.get('名称', '')} ({code.upper()})",
                })
            return results
        except Exception:
            return []
    
    @staticmethod
    def _safe_float(value) -> Optional[float]:
        """安全转换为浮点数"""
        if value is None or value == "" or value == "-":
            return None
        try:
            if isinstance(value, str):
                value = value.replace(",", "").replace("%", "")
            return float(value)
        except (ValueError, TypeError):
            return None

    def get_balance_sheet(self, stock_code: str) -> pd.DataFrame:
        """获取资产负债表
        
        Args:
            stock_code: 股票代码，如 sh600519 或 600519
        """
        code = self._normalize_code(stock_code)
        try:
            return ak.stock_financial_report_sina(stock=code, symbol="资产负债表")
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_income_statement(self, stock_code: str) -> pd.DataFrame:
        """获取利润表"""
        code = self._normalize_code(stock_code)
        try:
            return ak.stock_financial_report_sina(stock=code, symbol="利润表")
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_cash_flow(self, stock_code: str) -> pd.DataFrame:
        """获取现金流量表"""
        code = self._normalize_code(stock_code)
        try:
            return ak.stock_financial_report_sina(stock=code, symbol="现金流量表")
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_financial_summary(self, stock_code: str) -> dict[str, pd.DataFrame]:
        """获取完整财务报表"""
        return {
            "balance_sheet": self.get_balance_sheet(stock_code),
            "income_statement": self.get_income_statement(stock_code),
            "cash_flow": self.get_cash_flow(stock_code),
        }

    def get_stock_info(self, stock_code: str) -> dict[str, Any]:
        """获取股票基本信息"""
        code = stock_code.replace("sh", "").replace("sz", "")
        try:
            df = ak.stock_individual_info_em(symbol=code)
            info = {}
            for _, row in df.iterrows():
                info[row["item"]] = row["value"]
            return info
        except Exception as e:
            return {"error": str(e)}

    def get_financial_indicators(self, stock_code: str) -> pd.DataFrame:
        """获取主要财务指标
        
        使用同花顺财务摘要数据，包含 ROE、毛利率、净利率、资产负债率等
        """
        code = stock_code.replace("sh", "").replace("sz", "")
        try:
            df = ak.stock_financial_abstract_ths(symbol=code)
            if df.empty:
                return pd.DataFrame({"error": ["No data available"]})
            
            latest = df.iloc[-1].to_dict()
            
            def parse_percent(val):
                if val is None or val == "False" or val == False:
                    return None
                if isinstance(val, str):
                    return float(val.replace("%", "").replace(",", "")) / 100
                return float(val)
            
            def parse_number(val):
                if val is None or val == "False" or val == False:
                    return None
                if isinstance(val, str):
                    val = val.replace(",", "").replace("万", "")
                    try:
                        return float(val)
                    except:
                        return None
                return float(val)
            
            return pd.DataFrame([{
                "report_date": latest.get("报告期"),
                "roe": parse_percent(latest.get("净资产收益率")),
                "gross_margin": parse_percent(latest.get("销售毛利率")),
                "profit_margin": parse_percent(latest.get("销售净利率")),
                "debt_ratio": parse_percent(latest.get("资产负债率")),
                "current_ratio": parse_number(latest.get("流动比率")),
                "quick_ratio": parse_number(latest.get("速动比率")),
                "eps": parse_number(latest.get("基本每股收益")),
                "bvps": parse_number(latest.get("每股净资产")),
                "revenue_yoy": parse_percent(latest.get("营业总收入同比增长率")),
                "profit_yoy": parse_percent(latest.get("净利润同比增长率")),
            }])
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_profit_forecast(self, stock_code: str) -> pd.DataFrame:
        """获取盈利预测"""
        code = stock_code.replace("sh", "").replace("sz", "")
        try:
            return ak.stock_profit_forecast_em(symbol=code)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_macro_data(self, indicator: str = "cpi") -> pd.DataFrame:
        """获取宏观经济数据
        
        Args:
            indicator: 指标类型 (cpi, ppi, gdp, pmi)
        """
        try:
            if indicator == "cpi":
                return ak.macro_china_cpi_yearly()
            elif indicator == "ppi":
                return ak.macro_china_ppi_yearly()
            elif indicator == "gdp":
                return ak.macro_china_gdp_yearly()
            elif indicator == "pmi":
                return ak.macro_china_pmi_yearly()
            else:
                return pd.DataFrame({"error": [f"未知指标: {indicator}"]})
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def search_stock(self, keyword: str) -> pd.DataFrame:
        """搜索股票"""
        try:
            df = ak.stock_zh_a_spot_em()
            mask = (
                df["名称"].str.contains(keyword, na=False) |
                df["代码"].str.contains(keyword, na=False)
            )
            return df[mask][["代码", "名称", "最新价", "涨跌幅"]].head(20)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_industry_stocks(self, industry: str) -> pd.DataFrame:
        """获取行业成分股"""
        try:
            return ak.stock_board_industry_cons_em(symbol=industry)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_hk_history(
        self,
        ticker: str,
        period: str = "daily",
        start_date: str = None,
        end_date: str = None,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """获取港股历史K线数据
        
        Args:
            ticker: 港股代码，如 hk00700 或 00700
            period: 周期 daily/weekly/monthly
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adjust: 复权类型 qfq前复权/hfq后复权/不复权为空
        
        Returns:
            DataFrame with date, open, close, high, low, volume, etc.
        """
        code = ticker.lower().replace("hk", "").replace(".hk", "").zfill(5)
        
        if start_date is None:
            # 默认获取最近一年
            from datetime import timedelta
            end = datetime.now()
            start = end - timedelta(days=365)
            start_date = start.strftime("%Y%m%d")
            end_date = end.strftime("%Y%m%d")
        
        try:
            df = ak.stock_hk_hist(
                symbol=code,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            
            if df.empty:
                return pd.DataFrame()
            
            # 标准化列名
            df.rename(columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
            }, inplace=True)
            
            df["date"] = pd.to_datetime(df["date"])
            df.set_index("date", inplace=True)
            
            return df
            
        except Exception as e:
            print(f"[AKShareClient] HK history error: {e}")
            return pd.DataFrame()

    def get_us_history(
        self,
        ticker: str,
        period: str = "daily",
        start_date: str = None,
        end_date: str = None,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """获取美股历史K线数据
        
        Args:
            ticker: 美股代码，如 AAPL
            period: 周期 daily/weekly/monthly
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adjust: 复权类型 qfq前复权/hfq后复权/不复权为空
        
        Returns:
            DataFrame with date, open, close, high, low, volume, etc.
        """
        code = ticker.upper()
        
        # AKShare 美股代码格式: 105.AAPL (纳斯达克) 或 106.XXX (纽交所)
        # 需要先确定交易所前缀
        exchange_prefixes = ["105.", "106."]  # 纳斯达克, 纽交所
        
        if start_date is None:
            from datetime import timedelta
            end = datetime.now()
            start = end - timedelta(days=365)
            start_date = start.strftime("%Y%m%d")
            end_date = end.strftime("%Y%m%d")
        
        for prefix in exchange_prefixes:
            try:
                full_code = f"{prefix}{code}"
                df = ak.stock_us_hist(
                    symbol=full_code,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )
                
                if not df.empty:
                    # 标准化列名
                    df.rename(columns={
                        "日期": "date",
                        "开盘": "open",
                        "收盘": "close",
                        "最高": "high",
                        "最低": "low",
                        "成交量": "volume",
                        "成交额": "amount",
                    }, inplace=True)
                    
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                    
                    return df
                    
            except Exception as e:
                continue
        
        print(f"[AKShareClient] US history error: Could not find {ticker}")
        return pd.DataFrame()

    def _normalize_code(self, code: str) -> str:
        """标准化股票代码为 AKShare 格式"""
        code = code.lower()
        if code.startswith("sh") or code.startswith("sz"):
            return code
        if code.startswith("6"):
            return f"sh{code}"
        else:
            return f"sz{code}"
