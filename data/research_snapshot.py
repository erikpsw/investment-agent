"""Structured quote, trend, technical, and news snapshots for securities."""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from investment.data.news_fetcher import get_stock_news
from investment.data.market_cache import MarketDataCache, get_market_data_cache
from investment.data.stock_fetcher import StockFetcher


WINDOWS = (5, 10, 20, 60, 250)
RESEARCH_CACHE_KIND = "research-v4"


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
        market_cache: Optional[MarketDataCache] = None,
    ) -> None:
        self.fetcher = fetcher or StockFetcher()
        self.news_provider = news_provider or get_stock_news
        self.market_cache = market_cache or get_market_data_cache()

    @staticmethod
    def _quote_research(quote: Dict[str, Any], market: str) -> Dict[str, Any]:
        currency = str(quote.get("currency") or {"CN": "CNY", "HK": "HKD", "US": "USD"}.get(market.upper(), ""))
        return {
            "quote": {
                "price": _rounded(quote.get("price")),
                "currency": currency,
                "day_change_percent": _rounded(quote.get("change_percent")),
                "volume": _rounded(quote.get("volume")),
                "turnover_rate": _rounded(quote.get("turnover_rate")),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            "history": None,
            "errors": [f"quote: {str(quote['error'])[:160]}"] if quote.get("error") else [],
        }

    def enrich_quotes(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Attach quote-only research without fetching history or news."""
        if not items:
            return []
        quotes: Dict[str, Dict[str, Any]] = {}
        missing: List[Dict[str, Any]] = []
        cached_quotes = self.market_cache.get_many(
            [(str(item.get("market") or ""), str(item.get("ticker") or "")) for item in items],
            "quote",
        )
        for item in items:
            ticker = str(item.get("ticker") or "")
            market = str(item.get("market") or "")
            cached = cached_quotes.get((market.upper(), ticker.upper()))
            if cached is None:
                missing.append(item)
            else:
                quotes[ticker] = cached
        if missing:
            try:
                fetched = self.fetcher.get_quotes(missing)
            except AttributeError:
                with ThreadPoolExecutor(max_workers=min(6, len(missing))) as executor:
                    fetched = dict(executor.map(
                        lambda item: (str(item.get("ticker") or ""), self.fetcher.get_quote(str(item.get("ticker") or ""))),
                        missing,
                    ))
            cache_entries = []
            for item in missing:
                ticker = str(item.get("ticker") or "")
                quote = dict(fetched.get(ticker) or {"ticker": ticker, "error": "Quote unavailable"})
                quotes[ticker] = quote
                if not quote.get("error"):
                    cache_entries.append((str(item.get("market") or ""), ticker, quote))
            self.market_cache.set_many(cache_entries, "quote")
        return [
            {**item, "research": self._quote_research(quotes.get(str(item.get("ticker") or ""), {}), str(item.get("market") or ""))}
            for item in items
        ]

    def snapshot(
        self,
        ticker: str,
        name: str,
        market: str,
        include_history: bool = False,
        read_cache: bool = True,
    ) -> Dict[str, Any]:
        cached = self.market_cache.get(market, ticker, RESEARCH_CACHE_KIND) if read_cache else None
        if cached is not None:
            return {**cached, "history": cached.get("history") if include_history else None}
        errors: List[str] = []
        quote: Dict[str, Any] = {}
        history = pd.DataFrame()
        news: List[Dict[str, Any]] = []

        # Fetch independent providers concurrently so detail latency is bounded
        # by the slowest source rather than their combined response times.
        with ThreadPoolExecutor(max_workers=3) as executor:
            quote_future = executor.submit(self.fetcher.get_quote, ticker)
            history_future = executor.submit(lambda: self.fetcher.get_history(ticker, period="2y", interval="1d"))
            news_future = executor.submit(self.news_provider, ticker=ticker, stock_name=name, market=market, limit=5)
            try:
                quote = dict(quote_future.result() or {})
                if quote.get("error"):
                    errors.append(f"quote: {str(quote['error'])[:160]}")
            except Exception as exc:
                errors.append(_error("quote", exc))
            try:
                fetched = history_future.result()
                history = fetched.copy() if isinstance(fetched, pd.DataFrame) else pd.DataFrame(fetched)
            except Exception as exc:
                errors.append(_error("history", exc))
            try:
                news = list(news_future.result() or [])
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
        result = {
            "quote": {
                "price": _rounded(quote.get("price")),
                "currency": currency,
                "day_change_percent": _rounded(quote.get("change_percent")),
                "volume": _rounded(quote.get("volume")),
                "turnover_rate": _rounded(quote.get("turnover_rate")),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            **metrics,
            "recent_news": recent_news,
            "history": _history_records(history),
            "errors": errors,
        }
        if not errors:
            self.market_cache.set(market, ticker, RESEARCH_CACHE_KIND, result)
        return {**result, "history": result["history"] if include_history else None}

    @lru_cache(maxsize=1024)
    def _recent_return(self, ticker: str, cache_window: int) -> Dict[str, Any]:
        history = self.fetcher.get_history(ticker, period="1mo", interval="1d")
        frame = history if isinstance(history, pd.DataFrame) else pd.DataFrame(history)
        close = _numeric_column(frame, "close").dropna()
        value = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1) * 100 if len(close) >= 6 and float(close.iloc[-6]) else None
        return {"five_day_change_percent": _rounded(value), "five_day_asof": str(_time_values(frame).iloc[-1]) if not frame.empty else None}

    def quote(self, item: Dict[str, Any]) -> Dict[str, Any]:
        ticker = str(item.get("ticker") or "")
        market = str(item.get("market") or "").upper()
        errors = []
        try:
            quote = dict(self.fetcher.get_quote(ticker) or {})
            if quote.get("error"):
                raise ValueError(str(quote["error"]))
            result = {
                "price": _rounded(quote.get("price")),
                "currency": quote.get("currency") or {"CN": "CNY", "HK": "HKD", "US": "USD"}.get(market, ""),
                "day_change_percent": _rounded(quote.get("change_percent")),
                "volume": _rounded(quote.get("volume")),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            result = {"price": None, "fetched_at": datetime.now(timezone.utc).isoformat()}
            errors.append(_error("quote", exc))
        try:
            recent = self._recent_return(ticker, int(time.time() // 300))
        except Exception as exc:
            recent = {"five_day_change_percent": None, "five_day_asof": None}
            errors.append(_error("5d history", exc))
        return {**item, "research": {"quote": {**result, **recent}, "errors": errors}}

    def enrich(
        self,
        items: List[Dict[str, Any]],
        include_history: bool = False,
    ) -> List[Dict[str, Any]]:
        if not items:
            return []

        cached_research = self.market_cache.get_many(
            [(str(item.get("market") or ""), str(item.get("ticker") or "")) for item in items],
            RESEARCH_CACHE_KIND,
        )
        cached_by_position: Dict[int, Dict[str, Any]] = {}
        missing: List[tuple[int, Dict[str, Any]]] = []
        for index, item in enumerate(items):
            market = str(item.get("market") or "").upper()
            ticker = str(item.get("ticker") or "").upper()
            cached = cached_research.get((market, ticker))
            if cached is None:
                missing.append((index, item))
            else:
                cached_by_position[index] = {
                    **cached,
                    "history": cached.get("history") if include_history else None,
                }

        def enrich_one(indexed_item: tuple[int, Dict[str, Any]]) -> tuple[int, Dict[str, Any]]:
            index, item = indexed_item
            return {
                index: {
                    **item,
                    "research": self.snapshot(
                        ticker=str(item.get("ticker") or ""),
                        name=str(item.get("name") or ""),
                        market=str(item.get("market") or ""),
                        include_history=include_history,
                        read_cache=False,
                    ),
                },
            }

        enriched_by_position: Dict[int, Dict[str, Any]] = {
            index: {**items[index], "research": research}
            for index, research in cached_by_position.items()
        }
        if missing:
            with ThreadPoolExecutor(max_workers=min(6, len(missing))) as executor:
                for enriched in executor.map(enrich_one, missing):
                    enriched_by_position.update(enriched)
        return [enriched_by_position[index] for index in range(len(items))]
