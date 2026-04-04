"""
新浪财经 API 客户端 - 港股/美股实时行情与历史K线
"""
import requests
import pandas as pd
from typing import Any, Optional, Dict, List
from datetime import datetime


class SinaClient:
    """港股/美股行情客户端，基于新浪财经 API"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "http://finance.sina.com.cn",
        })
        self.base_url = "http://hq.sinajs.cn/list="

    def get_hk_quote(self, ticker: str) -> Dict[str, Any]:
        """获取港股实时行情
        
        Args:
            ticker: 港股代码，如 hk00700 或 00700
        """
        code = ticker.lower().replace("hk", "").replace(".hk", "")
        code = code.zfill(5)
        
        url = f"{self.base_url}rt_hk{code}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.encoding = "gbk"
            return self._parse_hk_quote(f"hk{code}", resp.text)
        except Exception as e:
            return {
                "ticker": f"hk{code}",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_us_quote(self, ticker: str) -> Dict[str, Any]:
        """获取美股实时行情
        
        Args:
            ticker: 美股代码，如 AAPL、MSFT
        """
        code = ticker.upper()
        
        url = f"{self.base_url}gb_{code.lower()}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.encoding = "gbk"
            return self._parse_us_quote(code, resp.text)
        except Exception as e:
            return {
                "ticker": code,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _parse_hk_quote(self, ticker: str, text: str) -> Dict[str, Any]:
        """解析港股行情数据
        
        格式: var hq_str_rt_hkXXXXX="英文名,中文名,昨收,今开,最高,最低,现价,涨跌,涨幅%,买价,卖价,成交额,成交量,市盈率,...日期,时间,..."
        """
        try:
            if '=""' in text or "FAILED" in text or not text.strip():
                return {"ticker": ticker, "error": "股票未找到", "timestamp": datetime.now().isoformat()}
            
            start = text.find('"') + 1
            end = text.rfind('"')
            if start <= 0 or end <= start:
                return {"ticker": ticker, "error": "解析失败", "timestamp": datetime.now().isoformat()}
            
            parts = text[start:end].split(",")
            if len(parts) < 15:
                return {"ticker": ticker, "error": "数据不完整", "timestamp": datetime.now().isoformat()}
            
            return {
                "ticker": ticker,
                "name": parts[1],  # 中文名
                "name_en": parts[0],  # 英文名
                "prev_close": self._safe_float(parts[2]),
                "open": self._safe_float(parts[3]),
                "high": self._safe_float(parts[4]),
                "low": self._safe_float(parts[5]),
                "price": self._safe_float(parts[6]),
                "change": self._safe_float(parts[7]),
                "change_percent": self._safe_float(parts[8]),
                "bid": self._safe_float(parts[9]),
                "ask": self._safe_float(parts[10]),
                "amount": self._safe_float(parts[11]),
                "volume": self._safe_float(parts[12]),
                "pe_ratio": self._safe_float(parts[13]),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"ticker": ticker, "error": f"解析异常: {e}", "timestamp": datetime.now().isoformat()}

    def _parse_us_quote(self, ticker: str, text: str) -> Dict[str, Any]:
        """解析美股行情数据
        
        格式: var hq_str_gb_xxxx="名称,现价,涨幅%,时间,涨跌,今开,最高,最低,52周最高,52周最低,成交量,成交额,市值,市盈率,每股收益,..."
        """
        try:
            if '=""' in text or "FAILED" in text or not text.strip():
                return {"ticker": ticker, "error": "股票未找到", "timestamp": datetime.now().isoformat()}
            
            start = text.find('"') + 1
            end = text.rfind('"')
            if start <= 0 or end <= start:
                return {"ticker": ticker, "error": "解析失败", "timestamp": datetime.now().isoformat()}
            
            parts = text[start:end].split(",")
            if len(parts) < 12:
                return {"ticker": ticker, "error": "数据不完整", "timestamp": datetime.now().isoformat()}
            
            return {
                "ticker": ticker,
                "name": parts[0],  # 中文名
                "price": self._safe_float(parts[1]),
                "change_percent": self._safe_float(parts[2]),
                "change": self._safe_float(parts[4]),
                "open": self._safe_float(parts[5]),
                "high": self._safe_float(parts[6]),
                "low": self._safe_float(parts[7]),
                "high_52week": self._safe_float(parts[8]),
                "low_52week": self._safe_float(parts[9]),
                "volume": self._safe_float(parts[10]),
                "amount": self._safe_float(parts[11]),
                "market_cap": self._safe_float(parts[12]),
                "pe_ratio": self._safe_float(parts[13]),
                "eps": self._safe_float(parts[14]),
                "prev_close": self._safe_float(parts[26]) if len(parts) > 26 else None,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"ticker": ticker, "error": f"解析异常: {e}", "timestamp": datetime.now().isoformat()}

    def get_us_history(self, ticker: str, limit: int = 250) -> pd.DataFrame:
        """获取美股历史K线数据
        
        Args:
            ticker: 美股代码，如 AAPL
            limit: 获取数据条数，最大约10000条
        
        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        code = ticker.lower()
        url = f"http://stock.finance.sina.com.cn/usstock/api/json.php/US_MinKService.getDailyK?symbol={code}&_=1"
        
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            
            data = resp.json()
            if not data or not isinstance(data, list):
                return pd.DataFrame()
            
            # 只取最新的 limit 条
            data = data[-limit:] if len(data) > limit else data
            
            df = pd.DataFrame(data)
            df.rename(columns={
                'd': 'date',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            }, inplace=True)
            
            # 转换类型
            df['date'] = pd.to_datetime(df['date'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df.set_index('date', inplace=True)
            return df
            
        except Exception as e:
            print(f"[SinaClient] US history error: {e}")
            return pd.DataFrame()

    @staticmethod
    def _safe_float(value: str) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            if value is None or value == "" or value == "-":
                return None
            return float(value)
        except (ValueError, TypeError):
            return None
