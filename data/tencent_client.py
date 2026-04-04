import requests
from typing import Any, Optional, Dict, List
from datetime import datetime


class TencentClient:
    """A股/港股行情客户端，基于腾讯财经 API"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        self.base_url = "https://qt.gtimg.cn/q="

    def get_quote(self, ticker: str) -> dict[str, Any]:
        """获取 A 股实时行情
        
        Args:
            ticker: 股票代码，如 sh600519（贵州茅台）、sz000001（平安银行）
        """
        url = f"{self.base_url}{ticker}"
        try:
            resp = self.session.get(url, timeout=5)
            resp.encoding = "gbk"
            return self._parse_quote(ticker, resp.text)
        except Exception as e:
            return {
                "ticker": ticker,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_hk_quote(self, ticker: str) -> dict[str, Any]:
        """获取港股实时行情
        
        Args:
            ticker: 港股代码，如 hk00700（腾讯）
        """
        url = f"{self.base_url}{ticker}"
        try:
            resp = self.session.get(url, timeout=5)
            return self._parse_hk_quote(ticker, resp.text)
        except Exception as e:
            return {
                "ticker": ticker,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_index(self, code: str, name: str) -> dict[str, Any]:
        """获取指数行情"""
        url = f"{self.base_url}{code}"
        try:
            resp = self.session.get(url, timeout=5)
            resp.encoding = "gbk"
            return self._parse_index(code, name, resp.text)
        except Exception as e:
            return {
                "code": code,
                "name": name,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_market_overview(self) -> dict[str, Any]:
        """获取市场概览（主要指数）"""
        indices = [
            ("sh000001", "上证指数"),
            ("sz399001", "深证成指"),
            ("sz399006", "创业板指"),
            ("sh000016", "上证50"),
            ("sh000300", "沪深300"),
        ]
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "indices": [],
        }
        
        for code, name in indices:
            index_data = self.get_index(code, name)
            if "error" not in index_data:
                result["indices"].append(index_data)
        
        return result

    def _parse_quote(self, ticker: str, text: str) -> dict[str, Any]:
        """解析 A 股行情数据"""
        for line in text.split("\n"):
            if f"v_{ticker}" in line:
                start = line.find('"') + 1
                end = line.rfind('"')
                if start > 0 and end > start:
                    parts = line[start:end].split("~")
                    if len(parts) > 45:
                        return {
                            "ticker": ticker,
                            "name": parts[1],
                            "price": self._safe_float(parts[3]),
                            "prev_close": self._safe_float(parts[4]),
                            "open": self._safe_float(parts[5]),
                            "volume": self._safe_float(parts[6]),
                            "buy_volume": self._safe_float(parts[7]),
                            "sell_volume": self._safe_float(parts[8]),
                            "change": self._safe_float(parts[31]),
                            "change_percent": self._safe_float(parts[32]),
                            "high": self._safe_float(parts[33]),
                            "low": self._safe_float(parts[34]),
                            "amount": self._safe_float(parts[37]),
                            "turnover_rate": self._safe_float(parts[38]),
                            "pe_ratio": self._safe_float(parts[39]),
                            "amplitude": self._safe_float(parts[43]),
                            "market_cap": self._safe_float(parts[45]),
                            "timestamp": datetime.now().isoformat(),
                        }
        
        return {"ticker": ticker, "error": "解析失败", "timestamp": datetime.now().isoformat()}

    def _parse_hk_quote(self, ticker: str, text: str) -> dict[str, Any]:
        """解析港股行情数据"""
        for line in text.split("\n"):
            if f"v_{ticker}" in line:
                parts = line.split("~")
                if len(parts) > 5:
                    return {
                        "ticker": ticker,
                        "name": parts[1] if len(parts) > 1 else ticker,
                        "price": self._safe_float(parts[3]) if len(parts) > 3 else None,
                        "change_percent": self._safe_float(parts[5]) if len(parts) > 5 else None,
                        "timestamp": datetime.now().isoformat(),
                    }
        
        return {"ticker": ticker, "error": "解析失败", "timestamp": datetime.now().isoformat()}

    def _parse_index(self, code: str, name: str, text: str) -> dict[str, Any]:
        """解析指数行情数据"""
        for line in text.split("\n"):
            if f"v_{code}" in line:
                start = line.find('"') + 1
                end = line.rfind('"')
                if start > 0 and end > start:
                    parts = line[start:end].split("~")
                    if len(parts) > 37:
                        return {
                            "code": code,
                            "name": name,
                            "price": self._safe_float(parts[3]),
                            "change_percent": self._safe_float(parts[32]),
                            "volume": self._safe_float(parts[6]),
                            "amount": self._safe_float(parts[37]),
                            "timestamp": datetime.now().isoformat(),
                        }
        
        return {"code": code, "name": name, "error": "解析失败", "timestamp": datetime.now().isoformat()}

    @staticmethod
    def _safe_float(value: str) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None
