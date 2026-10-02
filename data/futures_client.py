"""Domestic futures market data backed by AKShare's Sina adapters."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import akshare as ak
import pandas as pd


_PERIOD_ROWS = {"1d": 1, "5d": 5, "1mo": 22, "3mo": 66, "6mo": 132, "1y": 252}
_VARIETIES = {
    "A": "豆一", "AG": "白银", "AL": "沪铝", "AO": "氧化铝", "AP": "鲜苹果", "AU": "黄金",
    "B": "豆二", "BB": "胶合板", "BC": "国际铜", "BR": "丁二烯橡胶", "BU": "沥青",
    "C": "玉米", "CF": "棉花", "CJ": "红枣", "CS": "玉米淀粉", "CU": "沪铜", "CY": "棉纱",
    "EC": "集运指数(欧线)期货", "EG": "乙二醇", "EB": "苯乙烯", "FB": "纤维板", "FG": "玻璃",
    "FU": "燃油", "HC": "热轧卷板", "I": "铁矿石", "IC": "中证500指数期货", "IF": "沪深300指数期货",
    "IH": "上证50指数期货", "IM": "中证1000股指期货", "J": "焦炭", "JD": "鸡蛋", "JM": "焦煤", "JR": "粳稻",
    "L": "塑料", "LC": "碳酸锂", "LG": "原木", "LH": "生猪", "LU": "低硫燃料油", "M": "豆粕", "MA": "郑醇",
    "NI": "沪镍", "NR": "20号胶", "OI": "菜油", "P": "棕榈", "PB": "沪铅", "PC": "丙烯", "PD": "钯", "PF": "短纤",
    "PG": "液化石油气", "PK": "花生", "PM": "普麦", "PP": "PP", "PR": "瓶级聚酯切片", "PS": "多晶硅", "PT": "铂",
    "PX": "二甲苯", "RB": "螺纹钢", "RI": "早籼稻", "RM": "菜粕", "RR": "粳米", "RS": "菜籽", "RU": "橡胶",
    "SA": "纯碱", "SC": "原油", "SF": "硅铁", "SH": "烧碱", "SI": "工业硅", "SM": "锰硅", "SN": "沪锡", "SP": "纸浆",
    "SR": "白糖", "SS": "不锈钢", "T": "10年期国债期货", "TA": "PTA", "TF": "5年期国债期货", "TL": "30年期国债期货",
    "TS": "2年期国债期货", "UR": "尿素", "V": "PVC", "WH": "强麦", "WR": "线材", "Y": "豆油", "ZC": "动力煤", "ZN": "沪锌",
}


class FuturesClient:
    """Read-only quotes, contract search, and daily history for CN futures."""

    def _symbol_marks(self) -> pd.DataFrame:
        return ak.futures_symbol_mark()

    def _get_realtime_by_variety(self, variety: str) -> pd.DataFrame:
        return ak.futures_zh_realtime(symbol=variety)

    def _get_daily_history(self, symbol: str) -> pd.DataFrame:
        return ak.futures_zh_daily_sina(symbol=symbol)

    def _variety_for(self, ticker: str) -> str:
        query = ticker.strip()
        if not query:
            raise ValueError("期货合约不能为空")
        if not re.fullmatch(r"[A-Za-z]+\d*", query):
            return query

        prefix = re.match(r"[A-Za-z]+", query).group(0).upper()
        variety = _VARIETIES.get(prefix)
        if not variety:
            raise ValueError(f"未找到期货品种: {ticker}")
        return variety

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or pd.isna(value) or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def search(self, query: str, limit: int = 20) -> list[dict[str, str]]:
        needle = query.strip().casefold()
        if not needle:
            return []
        marks = self._symbol_marks()
        exchange_by_variety = {
            str(row.symbol): str(row.exchange).upper() for row in marks.itertuples(index=False)
        }
        matched = [
            (code, variety) for code, variety in _VARIETIES.items()
            if needle in code.casefold() or needle in variety.casefold()
        ][:limit]
        return [
            {
                "code": f"{code}0",
                "name": f"{variety}连续",
                "exchange": exchange_by_variety.get(variety, ""),
                "instrument_type": "futures",
            }
            for code, variety in matched
        ]

    def get_quote(self, ticker: str) -> dict[str, Any]:
        normalized = ticker.strip().upper()
        variety = self._variety_for(ticker)
        quotes = self._get_realtime_by_variety(variety)
        if quotes.empty:
            return {"ticker": normalized, "error": "未找到期货合约"}

        symbols = quotes["symbol"].astype(str).str.upper()
        row = quotes.loc[symbols == normalized]
        if row.empty and normalized.endswith("0"):
            row = quotes.loc[symbols == normalized]
        if row.empty:
            return {"ticker": normalized, "error": "未找到期货合约"}
        item = row.iloc[0]
        price = self._number(item.get("trade"))
        previous = self._number(item.get("presettlement"))
        timestamp = f"{item.get('tradedate')}T{item.get('ticktime')}"
        return {
            "ticker": str(item.get("symbol", normalized)).upper(),
            "name": str(item.get("name", "")),
            "exchange": str(item.get("exchange", "")).upper(),
            "price": price,
            "prev_close": previous,
            "open": self._number(item.get("open")),
            "high": self._number(item.get("high")),
            "low": self._number(item.get("low")),
            "volume": self._number(item.get("volume")),
            "open_interest": self._number(item.get("position")),
            "change": price - previous if price is not None and previous is not None else None,
            "change_percent": (self._number(item.get("changepercent")) or 0) * 100,
            "timestamp": timestamp if "None" not in timestamp else datetime.now().isoformat(),
            "market": "FUTURES_CN",
        }

    def get_history(self, ticker: str, period: str = "3mo") -> pd.DataFrame:
        symbol = ticker.strip().upper()
        if not re.fullmatch(r"[A-Z]+\d+", symbol):
            raise ValueError("历史行情仅支持期货合约或连续合约代码，例如 RB2601、RB0")
        frame = self._get_daily_history(symbol)
        if frame.empty:
            return frame
        frame = frame.rename(columns={"date": "date", "日期": "date"}).copy()
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date").sort_index()
        return frame.tail(_PERIOD_ROWS.get(period, _PERIOD_ROWS["3mo"]))
