"""
Pydantic schemas for API responses
"""
from typing import Optional, List, Any
from pydantic import BaseModel


class StockQuote(BaseModel):
    ticker: str
    name: Optional[str] = None
    price: Optional[float] = None
    prev_close: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    pe_ratio: Optional[float] = None
    market_cap: Optional[float] = None
    timestamp: Optional[str] = None
    market: Optional[str] = None


class SearchResult(BaseModel):
    code: str
    name: str
    market: str
    display: str
    exchange: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    query: str
    total: int


class HistoryBar(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class HistoryResponse(BaseModel):
    ticker: str
    period: str
    interval: str
    bars: List[HistoryBar]


class MarketIndex(BaseModel):
    code: str
    name: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None


class MarketOverview(BaseModel):
    indices: List[MarketIndex]
    timestamp: str


class FinancialMetrics(BaseModel):
    ticker: str
    name: Optional[str] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    gross_margin: Optional[float] = None
    profit_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
