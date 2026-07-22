"""Structured quote, trend, technical, and news snapshots for securities."""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from investment.data.news_fetcher import get_stock_news
from investment.data.stock_fetcher import StockFetcher


WINDOWS = (5, 20, 60, 250)


def _number(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _rounded(value: Any, digits: int = 4) -> Optional[float]:
    number = _number(value)
    return round(number, digits) if number is not None else None


def _numeric_column(frame: pd.DataFrame, name: str) -> pd.Series:
    for candidate in (name, name.lower(), name.capitalize(), name.upper()):
        if candidate in frame.columns:
            return pd.to_numeric(frame[candidate], errors="coerce")
    return pd.Series(dtype="float64")


def _time_values(frame: pd.DataFrame) -> pd.Series:
    for candidate in ("time", "date", "Date", "datetime", "Datetime"):
        if candidate in frame.columns:
            return frame[candidate].astype(str)
    return pd.Series(frame.index.astype(str), index=frame.index)


def _empty_metrics() -> Dict[str, Any]:
    return {
        "returns": {f"{window}d": None for window in WINDOWS},
        "moving_averages": {f"ma{window}": None for window in WINDOWS},
        "technical": {
            "volatility_20d": None,
            "volatility_60d": None,
            "rsi14": None,
            "volume_ratio_20d": None,
            "high_250d": None,
            "low_250d": None,
            "max_drawdown_250d": None,
            "distance_to_high_250d": None,
        },
    }


def _history_metrics(frame: pd.DataFrame) -> Dict[str, Any]:
    result = _empty_metrics()
    close = _numeric_column(frame, "close").dropna().reset_index(drop=True)
    if close.empty:
        return result

    for window in WINDOWS:
        if len(close) >= window + 1:
            base = float(close.iloc[-window - 1])
            if base:
                result["returns"][f"{window}d"] = _rounded(
                    (float(close.iloc[-1]) / base - 1) * 100
                )
        if len(close) >= window:
            result["moving_averages"][f"ma{window}"] = _rounded(
                close.tail(window).mean()
            )

    daily_returns = close.pct_change().dropna()
    for window in (20, 60):
        if len(daily_returns) >= window:
            volatility = daily_returns.tail(window).std(ddof=1) * math.sqrt(252) * 100
            result["technical"][f"volatility_{window}d"] = _rounded(volatility)

    if len(close) >= 15:
        changes = close.diff().dropna().tail(14)
        gains = changes.clip(lower=0).mean()
        losses = (-changes.clip(upper=0)).mean()
        if losses > 0:
            result["technical"]["rsi14"] = _rounded(
                100 - 100 / (1 + gains / losses)
            )
        elif gains > 0:
            result["technical"]["rsi14"] = 100.0
        else:
            result["technical"]["rsi14"] = 50.0

    volume = _numeric_column(frame, "volume").dropna().reset_index(drop=True)
    if len(volume) >= 20:
        average = float(volume.tail(20).mean())
        if average:
            result["technical"]["volume_ratio_20d"] = _rounded(
                float(volume.iloc[-1]) / average
            )

    window_close = close.tail(250)
    high = float(window_close.max())
    low = float(window_close.min())
    running_high = window_close.cummax()
    drawdowns = window_close / running_high - 1
    result["technical"].update(
        {
            "high_250d": _rounded(high),
            "low_250d": _rounded(low),
            "max_drawdown_250d": _rounded(float(drawdowns.min()) * 100),
            "distance_to_high_250d": _rounded(
                (float(window_close.iloc[-1]) / high - 1) * 100 if high else None
            ),
        }
    )
    return result


def _history_records(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    if frame.empty:
        return []
    times = _time_values(frame)
    records: List[Dict[str, Any]] = []
    for index in frame.index:
        record = {
            "time": str(times.loc[index]),
            "open": _rounded(frame.loc[index].get("open", frame.loc[index].get("Open"))),
            "high": _rounded(frame.loc[index].get("high", frame.loc[index].get("High"))),
            "low": _rounded(frame.loc[index].get("low", frame.loc[index].get("Low"))),
            "close": _rounded(frame.loc[index].get("close", frame.loc[index].get("Close"))),
            "volume": _rounded(frame.loc[index].get("volume", frame.loc[index].get("Volume"))),
        }
        if record["close"] is not None:
            records.append(record)
    records.sort(key=lambda item: item["time"])
    return records[-250:]


def _error(source: str, exc: Exception) -> str:
    return f"{source}: {str(exc).strip()[:160]}"


class ResearchSnapshotService:
    def __init__(
        self,
        fetcher: Optional[Any] = None,
        news_provider: Optional[Callable[..., List[Dict[str, Any]]]] = None,
    ) -> None:
        self.fetcher = fetcher or StockFetcher()
        self.news_provider = news_provider or get_stock_news

    def snapshot(
        self,
        ticker: str,
        name: str,
        market: str,
        include_history: bool = False,
    ) -> Dict[str, Any]:
        errors: List[str] = []
        quote: Dict[str, Any] = {}
        history = pd.DataFrame()
        news: List[Dict[str, Any]] = []

        try:
            quote = dict(self.fetcher.get_quote(ticker) or {})
            if quote.get("error"):
                errors.append(f"quote: {str(quote['error'])[:160]}")
        except Exception as exc:
            errors.append(_error("quote", exc))

        try:
            fetched = self.fetcher.get_history(ticker, period="2y", interval="1d")
            history = fetched.copy() if isinstance(fetched, pd.DataFrame) else pd.DataFrame(fetched)
        except Exception as exc:
            errors.append(_error("history", exc))

        try:
            news = list(
                self.news_provider(
                    ticker=ticker,
                    stock_name=name,
                    market=market,
                    limit=5,
                )
                or []
            )
        except Exception as exc:
            errors.append(_error("news", exc))

        metrics = _history_metrics(history)
        currency = str(quote.get("currency") or {"CN": "CNY", "HK": "HKD", "US": "USD"}.get(market.upper(), ""))
        recent_news = [
            {
                "title": item.get("title"),
                "published": item.get("published") or item.get("published_date"),
                "source": item.get("source"),
                "link": item.get("link") or item.get("url"),
                "summary": item.get("summary"),
            }
            for item in news[:5]
        ]
        return {
            "quote": {
                "price": _rounded(quote.get("price")),
                "currency": currency,
                "day_change_percent": _rounded(quote.get("change_percent")),
                "volume": _rounded(quote.get("volume")),
            },
            **metrics,
            "recent_news": recent_news,
            "history": _history_records(history) if include_history else None,
            "errors": errors,
        }

    def enrich(
        self,
        items: List[Dict[str, Any]],
        include_history: bool = False,
    ) -> List[Dict[str, Any]]:
        if not items:
            return []

        def enrich_one(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                **item,
                "research": self.snapshot(
                    ticker=str(item.get("ticker") or ""),
                    name=str(item.get("name") or ""),
                    market=str(item.get("market") or ""),
                    include_history=include_history,
                ),
            }

        with ThreadPoolExecutor(max_workers=min(6, len(items))) as executor:
            return list(executor.map(enrich_one, items))
