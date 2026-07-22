"""Portfolio storage and analysis helpers."""
from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from investment.agents.llm import get_llm_client
from investment.data.news_fetcher import get_stock_news
from investment.data.portfolio_store import PortfolioStore, get_portfolio_store
from investment.data.research_snapshot import ResearchSnapshotService
from investment.data.stock_fetcher import StockFetcher


def _detect_market(ticker: str) -> str:
    value = ticker.lower().strip()
    if value in {"cash", "现金"} or value.startswith("cash_"):
        return "CASH"
    if value.startswith(("sh", "sz")) or value.isdigit():
        return "CN"
    if value.startswith("hk") or value.endswith(".hk"):
        return "HK"
    return "US"


def _is_cash_position(position: Dict[str, Any]) -> bool:
    ticker = str(position.get("ticker") or "").strip().lower()
    market = str(position.get("market") or "").strip().upper()
    return ticker in {"cash", "现金"} or ticker.startswith("cash_") or market == "CASH"


def _currency_for_market(market: str, explicit: Any = None) -> str:
    currency = str(explicit or "").strip().upper()
    if currency in {"CNY", "HKD", "USD"}:
        return currency
    return {"CN": "CNY", "HK": "HKD", "US": "USD", "CASH": "CNY"}.get(
        market.upper(), "CNY"
    )


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        result = float(value)
        if math.isnan(result) or math.isinf(result):
            return None
        return result
    except (TypeError, ValueError):
        return None


def _safe_round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return round(value, digits) if value is not None else None


def _column(df: pd.DataFrame, name: str) -> Optional[pd.Series]:
    for candidate in (name, name.capitalize(), name.upper()):
        if candidate in df.columns:
            return pd.to_numeric(df[candidate], errors="coerce")
    return None


def _technical_summary(history: pd.DataFrame) -> Dict[str, Any]:
    if history is None or history.empty:
        return {"status": "no_data", "summary": "历史价格数据不足，暂不能判断技术面。"}
    close = _column(history, "close")
    volume = _column(history, "volume")
    if close is None or close.dropna().empty:
        return {"status": "no_data", "summary": "历史收盘价缺失，暂不能判断技术面。"}
    close = close.dropna()
    latest = float(close.iloc[-1])
    ma20 = float(close.tail(20).mean()) if len(close) >= 20 else None
    ma60 = float(close.tail(60).mean()) if len(close) >= 60 else None
    change_5d = (latest / float(close.iloc[-6]) - 1) * 100 if len(close) >= 6 and close.iloc[-6] else None
    change_20d = (latest / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 and close.iloc[-21] else None
    high_20d = float(close.tail(20).max()) if len(close) >= 20 else None
    distance_to_high_20d = (latest / high_20d - 1) * 100 if high_20d else None
    delta = close.diff()
    gains = delta.clip(lower=0).tail(14).mean()
    losses = (-delta.clip(upper=0)).tail(14).mean()
    rsi14 = None
    if losses and losses > 0:
        rs = gains / losses
        rsi14 = 100 - (100 / (1 + rs))
    elif gains and gains > 0:
        rsi14 = 100.0
    volume_ratio = None
    if volume is not None and len(volume.dropna()) >= 21:
        vol = volume.dropna()
        avg_volume = float(vol.tail(20).mean())
        if avg_volume:
            volume_ratio = float(vol.iloc[-1]) / avg_volume
    signals: List[str] = []
    if ma20 is not None:
        signals.append("站上20日均线" if latest >= ma20 else "低于20日均线")
    if ma60 is not None:
        signals.append("站上60日均线" if latest >= ma60 else "低于60日均线")
    if rsi14 is not None:
        if rsi14 >= 70:
            signals.append("RSI偏热")
        elif rsi14 <= 30:
            signals.append("RSI偏弱")
        else:
            signals.append("RSI中性")
    return {
        "status": "ok",
        "latest_close": _safe_round(latest),
        "ma20": _safe_round(ma20),
        "ma60": _safe_round(ma60),
        "change_5d": _safe_round(change_5d),
        "change_20d": _safe_round(change_20d),
        "distance_to_high_20d": _safe_round(distance_to_high_20d),
        "rsi14": _safe_round(rsi14),
        "volume_ratio": _safe_round(volume_ratio, 2),
        "summary": "；".join(signals) if signals else "技术信号不足。",
    }


class PortfolioService:
    def __init__(
        self,
        store: Optional[PortfolioStore] = None,
        fx_rate_provider: Optional[Callable[[], Dict[str, float]]] = None,
        research_service: Optional[ResearchSnapshotService] = None,
    ) -> None:
        self.fetcher = StockFetcher()
        self.store = store or get_portfolio_store()
        self.fx_rate_provider = fx_rate_provider or self._fetch_fx_rates
        self.research_service = research_service
        self._cached_fx_rates: Dict[str, float] = {}
        self._fx_cached_at = 0.0

    def _fetch_fx_rates(self) -> Dict[str, float]:
        rates = {"CNY": 1.0, "USD": 7.0, "HKD": 0.9}
        for currency, ticker in (("USD", "CNY=X"), ("HKD", "HKDCNY=X")):
            try:
                quote = self.fetcher.yfinance.get_quote(ticker)
                price = _to_float(quote.get("price"))
                if price and price > 0:
                    rates[currency] = price
            except Exception:
                pass
        return rates

    def _get_fx_rates(self) -> Dict[str, float]:
        now = time.time()
        if not self._cached_fx_rates or now - self._fx_cached_at >= 600:
            supplied = self.fx_rate_provider()
            self._cached_fx_rates = {
                "CNY": 1.0,
                "USD": float(supplied.get("USD", 7.0)),
                "HKD": float(supplied.get("HKD", 0.9)),
            }
            self._fx_cached_at = now
        return dict(self._cached_fx_rates)

    def get_positions(self, user_id: str, include_history: bool = False) -> Dict[str, Any]:
        document = self.store.load(user_id)
        positions = self._normalize_positions(document.positions)
        return {
            "updated_at": document.updated_at,
            "positions": self._snapshot_positions(positions, include_history=include_history),
            "storage": document.storage,
            "valuation_currency": "CNY",
            "fx_rates": self._get_fx_rates(),
        }

    def save_positions(self, user_id: str, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        normalized = self._normalize_positions(positions)
        document = self.store.save(user_id, normalized)
        return {
            "updated_at": document.updated_at,
            "positions": self._snapshot_positions(normalized),
            "storage": document.storage,
            "valuation_currency": "CNY",
            "fx_rates": self._get_fx_rates(),
        }

    def _normalize_positions(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen_cash: set[str] = set()
        for row in positions:
            ticker = str(row.get("ticker") or "").strip()
            if not ticker:
                continue
            market = str(row.get("market") or _detect_market(ticker)).upper()
            currency = _currency_for_market(market, row.get("currency"))
            quantity = _to_float(row.get("quantity")) or 0.0
            avg_cost = _to_float(row.get("avg_cost")) or 0.0
            name = str(row.get("name") or "").strip()
            if _is_cash_position({"ticker": ticker, "market": market}):
                suffix = ticker.upper().removeprefix("CASH_")
                if suffix in {"CNY", "HKD", "USD"}:
                    currency = suffix
                ticker = f"CASH_{currency}"
                if ticker in seen_cash:
                    continue
                seen_cash.add(ticker)
                market = "CASH"
                name = name or {"CNY": "人民币现金", "HKD": "港币现金", "USD": "美元现金"}[currency]
                avg_cost = 1.0
            normalized.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "market": market,
                    "currency": currency,
                    "quantity": quantity,
                    "avg_cost": avg_cost,
                    "notes": str(row.get("notes") or "").strip(),
                }
            )
        return normalized

    def analyze(self, user_id: str) -> Dict[str, Any]:
        document = self.store.load(user_id)
        positions = self._normalize_positions(document.positions)
        if not positions:
            return {
                "generated_at": datetime.now().isoformat(),
                "positions": [],
                "summary": "暂无持仓。请先录入股票代码、数量和买入均价。",
                "total_cost": 0,
                "total_market_value": 0,
                "total_pnl": 0,
                "total_pnl_percent": None,
                "agent_view": "暂无持仓数据，无法形成仓位管理建议。",
                "valuation_currency": "CNY",
                "fx_rates": {"CNY": 1.0},
            }
        fx_rates = self._get_fx_rates()
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(positions)))) as executor:
            futures = [executor.submit(self._analyze_position, position, fx_rates) for position in positions]
            items = [future.result() for future in as_completed(futures)]
        order = {position["ticker"]: index for index, position in enumerate(positions)}
        items.sort(key=lambda item: order.get(str(item.get("ticker")), 999))
        total_cost = sum(float(item.get("cost") or 0) for item in items)
        total_market_value = sum(float(item.get("market_value") or 0) for item in items)
        total_pnl = total_market_value - total_cost
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost else None
        for item in items:
            item["weight"] = _safe_round((float(item.get("market_value") or 0) / total_market_value * 100) if total_market_value else None)
        agent_view = self._agent_view(items, total_cost, total_market_value, total_pnl, total_pnl_percent)
        return {
            "generated_at": datetime.now().isoformat(),
            "positions": items,
            "summary": self._fallback_summary(items, total_pnl_percent),
            "total_cost": _safe_round(total_cost),
            "total_market_value": _safe_round(total_market_value),
            "total_pnl": _safe_round(total_pnl),
            "total_pnl_percent": _safe_round(total_pnl_percent),
            "agent_view": agent_view,
            "valuation_currency": "CNY",
            "fx_rates": fx_rates,
        }

    def _snapshot_positions(
        self,
        positions: List[Dict[str, Any]],
        include_history: bool = False,
    ) -> List[Dict[str, Any]]:
        if not positions:
            return []
        fx_rates = self._get_fx_rates()
        with ThreadPoolExecutor(max_workers=min(6, max(1, len(positions)))) as executor:
            items = list(executor.map(lambda position: self._quote_snapshot(position, fx_rates), positions))

        security_indexes = [index for index, item in enumerate(items) if not _is_cash_position(item)]
        if security_indexes:
            research_service = self.research_service or ResearchSnapshotService(fetcher=self.fetcher)
            enriched = research_service.enrich(
                [items[index] for index in security_indexes],
                include_history=include_history,
            )
            for index, researched in zip(security_indexes, enriched):
                items[index]["research"] = researched.get("research")
        total_market_value = sum(float(item.get("market_value") or 0) for item in items)
        for item in items:
            item["weight"] = _safe_round((float(item.get("market_value") or 0) / total_market_value * 100) if total_market_value else None)
        return items

    def _quote_snapshot(self, position: Dict[str, Any], fx_rates: Dict[str, float]) -> Dict[str, Any]:
        ticker = str(position.get("ticker") or "").strip()
        market = str(position.get("market") or _detect_market(ticker)).upper()
        quantity = float(position.get("quantity") or 0)
        avg_cost = float(position.get("avg_cost") or 0)
        currency = _currency_for_market(market, position.get("currency"))
        fx_rate = fx_rates[currency]
        if _is_cash_position(position):
            cost_native = quantity
            cost = cost_native * fx_rate
            return {
                **position,
                "ticker": ticker,
                "name": position.get("name") or {"CNY": "人民币现金", "HKD": "港币现金", "USD": "美元现金"}[currency],
                "market": "CASH",
                "currency": currency,
                "fx_rate_to_cny": _safe_round(fx_rate, 6),
                "avg_cost": 1.0,
                "current_price": 1.0,
                "cost": _safe_round(cost),
                "cost_native": _safe_round(cost_native),
                "market_value": _safe_round(cost),
                "market_value_native": _safe_round(quantity),
                "pnl": 0.0,
                "pnl_native": 0.0,
                "pnl_percent": 0.0,
                "day_change_percent": 0.0,
                "errors": [],
            }
        errors: List[str] = []
        quote: Dict[str, Any] = {}
        try:
            quote = self.fetcher.get_quote(ticker)
            if quote.get("error"):
                errors.append(str(quote.get("error")))
        except Exception as exc:
            errors.append(f"quote: {str(exc)[:120]}")
        price = _to_float(quote.get("price"))
        cost_native = quantity * avg_cost
        market_value_native = quantity * price if price is not None else None
        pnl_native = market_value_native - cost_native if market_value_native is not None else None
        cost = cost_native * fx_rate
        market_value = market_value_native * fx_rate if market_value_native is not None else None
        pnl = pnl_native * fx_rate if pnl_native is not None else None
        pnl_percent = pnl_native / cost_native * 100 if pnl_native is not None and cost_native else None
        return {
            **position,
            "name": str(position.get("name") or quote.get("name") or ""),
            "market": market,
            "currency": currency,
            "fx_rate_to_cny": _safe_round(fx_rate, 6),
            "current_price": _safe_round(price),
            "cost": _safe_round(cost),
            "cost_native": _safe_round(cost_native),
            "market_value": _safe_round(market_value),
            "market_value_native": _safe_round(market_value_native),
            "pnl": _safe_round(pnl),
            "pnl_native": _safe_round(pnl_native),
            "pnl_percent": _safe_round(pnl_percent),
            "day_change_percent": _safe_round(_to_float(quote.get("change_percent"))),
            "errors": errors,
        }

    def _analyze_position(self, position: Dict[str, Any], fx_rates: Dict[str, float]) -> Dict[str, Any]:
        ticker = str(position["ticker"])
        market = str(position.get("market") or _detect_market(ticker)).upper()
        quantity = float(position.get("quantity") or 0)
        avg_cost = float(position.get("avg_cost") or 0)
        currency = _currency_for_market(market, position.get("currency"))
        fx_rate = fx_rates[currency]
        if _is_cash_position(position):
            market_value = quantity * fx_rate
            return {
                "ticker": ticker,
                "name": position.get("name") or {"CNY": "人民币现金", "HKD": "港币现金", "USD": "美元现金"}[currency],
                "market": "CASH",
                "currency": currency,
                "fx_rate_to_cny": _safe_round(fx_rate, 6),
                "quantity": quantity,
                "avg_cost": 1.0,
                "current_price": 1.0,
                "cost": _safe_round(market_value),
                "cost_native": _safe_round(quantity),
                "market_value": _safe_round(market_value),
                "market_value_native": _safe_round(quantity),
                "pnl": 0.0,
                "pnl_native": 0.0,
                "pnl_percent": 0.0,
                "day_change_percent": 0.0,
                "technical": {"status": "cash", "summary": "现金仓位，无价格波动，用于控制组合风险和保留加仓弹性。"},
                "recent_news": [],
                "notes": position.get("notes") or "",
                "errors": [],
            }
        errors: List[str] = []
        quote: Dict[str, Any] = {}
        history = pd.DataFrame()
        news: List[Dict[str, Any]] = []
        try:
            quote = self.fetcher.get_quote(ticker)
            if quote.get("error"):
                errors.append(str(quote.get("error")))
        except Exception as exc:
            errors.append(f"quote: {str(exc)[:120]}")
        name = str(position.get("name") or quote.get("name") or "")
        try:
            history = self.fetcher.get_history(ticker, period="3mo", interval="1d")
        except Exception as exc:
            errors.append(f"history: {str(exc)[:120]}")
        try:
            news = get_stock_news(ticker=ticker, stock_name=name, market=market, limit=5)
        except Exception as exc:
            errors.append(f"news: {str(exc)[:120]}")
        price = _to_float(quote.get("price"))
        cost_native = quantity * avg_cost
        market_value_native = quantity * price if price is not None else None
        pnl_native = market_value_native - cost_native if market_value_native is not None else None
        cost = cost_native * fx_rate
        market_value = market_value_native * fx_rate if market_value_native is not None else None
        pnl = pnl_native * fx_rate if pnl_native is not None else None
        pnl_percent = pnl_native / cost_native * 100 if pnl_native is not None and cost_native else None
        technical = _technical_summary(history)
        return {
            "ticker": ticker,
            "name": name,
            "market": market,
            "currency": currency,
            "fx_rate_to_cny": _safe_round(fx_rate, 6),
            "quantity": quantity,
            "avg_cost": avg_cost,
            "current_price": _safe_round(price),
            "cost": _safe_round(cost),
            "cost_native": _safe_round(cost_native),
            "market_value": _safe_round(market_value),
            "market_value_native": _safe_round(market_value_native),
            "pnl": _safe_round(pnl),
            "pnl_native": _safe_round(pnl_native),
            "pnl_percent": _safe_round(pnl_percent),
            "day_change_percent": _safe_round(_to_float(quote.get("change_percent"))),
            "technical": technical,
            "recent_news": news[:5],
            "notes": position.get("notes") or "",
            "errors": errors,
        }

    def _agent_view(
        self,
        items: List[Dict[str, Any]],
        total_cost: float,
        total_market_value: float,
        total_pnl: float,
        total_pnl_percent: Optional[float],
    ) -> str:
        compact = []
        for item in items:
            compact.append(
                {
                    "ticker": item.get("ticker"),
                    "name": item.get("name"),
                    "weight": item.get("weight"),
                    "pnl_percent": item.get("pnl_percent"),
                    "day_change_percent": item.get("day_change_percent"),
                    "technical": item.get("technical"),
                    "news": [
                        {
                            "title": article.get("title"),
                            "summary": article.get("summary"),
                            "source": article.get("source"),
                        }
                        for article in item.get("recent_news", [])[:3]
                    ],
                }
            )
        prompt = f"""请分析当前投资组合，输出中文纯文本，不要 Markdown。
重点覆盖：
1. 组合总体风险和收益状态。
2. 新闻、价格、技术面如何影响每个持仓。
3. 仓位管理建议：哪些可继续持有，哪些应降低仓位或等待确认，哪些可观察加仓条件。
4. 不要给出绝对收益承诺，不构成投资建议。

组合汇总（以下金额均已折算为人民币）：
总成本 CNY {total_cost:.2f}，当前市值 CNY {total_market_value:.2f}，浮动盈亏 CNY {total_pnl:.2f}，盈亏比例 {total_pnl_percent if total_pnl_percent is not None else "未知"}%。

持仓数据：
{json.dumps(compact, ensure_ascii=False)[:12000]}"""
        try:
            response = get_llm_client().chat(
                prompt,
                system_prompt="你是谨慎的投资组合风控分析员，结合新闻、价格和技术面给出仓位管理建议。",
                temperature=0.2,
                max_tokens=1800,
            )
            if response and not response.startswith("[LLM "):
                return response.strip()
        except Exception:
            pass
        return self._fallback_summary(items, total_pnl_percent)

    def _fallback_summary(self, items: List[Dict[str, Any]], total_pnl_percent: Optional[float]) -> str:
        weak = [item for item in items if (item.get("pnl_percent") or 0) < -8 or "低于20日均线" in str(item.get("technical", {}).get("summary"))]
        heavy = [item for item in items if (item.get("weight") or 0) >= 35]
        pieces = [
            f"组合当前盈亏比例约为 {_safe_round(total_pnl_percent) if total_pnl_percent is not None else '--'}%。",
            f"持仓数量 {len(items)} 个。",
        ]
        if heavy:
            pieces.append("单一持仓权重偏高：" + "、".join(str(item.get("ticker")) for item in heavy[:3]) + "。")
        if weak:
            pieces.append("需要重点复核：" + "、".join(str(item.get("ticker")) for item in weak[:5]) + "。")
        pieces.append("建议结合最新新闻和技术位分批调整，避免一次性大幅加减仓。")
        return "".join(pieces)


_service: Optional[PortfolioService] = None


def get_portfolio_service() -> PortfolioService:
    global _service
    if _service is None:
        _service = PortfolioService()
    return _service
