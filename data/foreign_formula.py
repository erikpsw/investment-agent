"""Bounded HK/US candidate snapshots and historical enrichment."""
from __future__ import annotations
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from investment.data.formula_scoring import number
from investment.data.formula_instruments import stock_candidates

ROOT = Path(__file__).resolve().parents[1]
_cache = {}


def _validated_bars(bars: list[dict], cutoff: str) -> list[dict]:
    rows = sorted([row for row in bars if row["date"] <= cutoff], key=lambda row: row["date"])
    seen = set()
    for row in rows:
        day = row["date"]
        if datetime.fromisoformat(day).date().isoformat() != day or day in seen:
            raise RuntimeError("历史日K日期重复或格式异常")
        seen.add(day)
        values = [number(row.get(field)) for field in ("open", "high", "low", "close")]
        if any(value is None or value <= 0 for value in values):
            raise RuntimeError("历史OHLC存在缺失或非正价格，整只隔离")
        opening, high, low, close = values
        if not low <= min(opening, close) <= max(opening, close) <= high:
            raise RuntimeError("历史OHLC价格区间异常，整只隔离")
    return rows

def scan_foreign_market(market: str) -> dict:
    if market not in ("HK", "US"):
        raise ValueError("Expected HK or US")
    path = ROOT / "storage/market" / f"hot-{market.lower()}.json"
    if path.exists():
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        rows = [row for row in snapshot.get("rows", []) if row.get("market") == market and number(row.get("price")) is not None and number(row["price"]) > 0]
        if rows:
            filtered = stock_candidates(rows)
            rows = filtered["rows"]; stats = {key: value for key, value in filtered.items() if key != "rows"}
            return {**snapshot, "rows": rows, "instrument_filter": stats, "cached": True, "stale": True}
    from investment.data.hot_stocks import get_hot_stock_snapshot
    snapshot = get_hot_stock_snapshot(market)
    filtered = stock_candidates(snapshot.get("rows", []))
    rows = filtered["rows"]; stats = {key: value for key, value in filtered.items() if key != "rows"}
    return {**snapshot, "rows": rows, "instrument_filter": stats}

def completed_date(as_of: str | None, market: str) -> str:
    zone = ZoneInfo("Asia/Hong_Kong" if market == "HK" else "America/New_York")
    stamp = datetime.fromisoformat(as_of.replace("Z", "+00:00")) if as_of else datetime.now(zone)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=zone)
    stamp = stamp.astimezone(zone)
    if (not as_of or len(as_of) > 10) and stamp.hour < 16:
        stamp -= timedelta(days=1)
    return stamp.date().isoformat()

def foreign_bars(ticker: str, market: str, as_of: str | None = None) -> list[dict]:
    cutoff = completed_date(as_of, market)
    key = (market, ticker, cutoff)
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < 600:
        return cached[1]
    code = ticker if market == "HK" else "us" + ticker
    bars = []
    try:
        endpoint = "hkfqkline/get" if market == "HK" else "fqkline/get"
        response = requests.get(f"https://web.ifzq.gtimg.cn/appstock/app/{endpoint}", params={"param": f"{code},day,,{cutoff},640,qfq"}, timeout=8)
        response.raise_for_status()
        payload = response.json().get("data", {}).get(code, {})
        adjusted_rows = payload.get("qfqday")
        raw = adjusted_rows or payload.get("day") or []
        if any(len(row) < 6 for row in raw):
            raise RuntimeError("历史OHLC行不完整")
        bars = [{"date": row[0], "open": number(row[1]), "close": number(row[2]), "high": number(row[3]), "low": number(row[4]), "volume": number(row[5]), "raw_close": number(row[2]) if not adjusted_rows else None, "history_source": "Tencent", "price_basis": "qfq" if adjusted_rows else "raw"} for row in raw]
        bars = _validated_bars(bars, cutoff)
    except Exception:
        bars = []
    if len(bars) < 61:
        symbol = f"{ticker[2:].lstrip('0').zfill(4)}.HK" if market == "HK" else ticker.upper().replace(".", "-")
        end = int(datetime.fromisoformat(cutoff).replace(tzinfo=ZoneInfo("UTC")).timestamp()) + 86400
        response = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", params={"period1": end - 86400 * 1100, "period2": end, "interval": "1d"}, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        response.raise_for_status()
        payload = response.json()["chart"]["result"][0]
        meta = payload.get("meta", {})
        returned_symbol = meta.get("symbol")
        if not isinstance(returned_symbol, str) or returned_symbol.upper() != symbol.upper():
            raise RuntimeError("历史响应证券代码与请求不匹配或未提供")
        if meta.get("currency") != ("HKD" if market == "HK" else "USD"):
            raise RuntimeError("历史响应币种与股票市场不匹配或未提供")
        if meta.get("instrumentType") != "EQUITY":
            raise RuntimeError("历史响应证券类型不是已核验的股票")
        values = payload["indicators"]["quote"][0]
        adjusted = payload["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
        stamps = payload.get("timestamp", [])
        if not isinstance(adjusted, list) or len(adjusted) != len(stamps) or not adjusted:
            raise RuntimeError("历史复权价格数组缺失或未对齐")
        for field in ("open", "high", "low", "close", "volume"):
            array = values.get(field, [None] * len(stamps)) if field == "volume" else values.get(field)
            if not isinstance(array, list) or len(array) != len(stamps):
                raise RuntimeError("历史OHLCV价格数组未对齐")
        zone = ZoneInfo("Asia/Hong_Kong" if market == "HK" else "America/New_York")
        bars = []
        for index, stamp in enumerate(stamps):
            close = number(values["close"][index])
            if close is None or close <= 0:
                raise RuntimeError("历史OHLC收盘价缺失或非正，整只隔离")
            adj = number(adjusted[index])
            if adj is None or adj <= 0:
                raise RuntimeError("历史复权收盘价缺失或非正，整只隔离")
            factor = adj / close
            row = {"date": datetime.fromtimestamp(stamp, zone).date().isoformat()}
            for field in ("open", "high", "low", "close"):
                value = number(values[field][index]); row[field] = value * factor if value is not None else None
            row["volume"] = number(values.get("volume", [None] * len(payload["timestamp"]))[index])
            row["raw_close"] = close
            row["share_scale"] = 1 / factor
            row["history_source"] = "Yahoo"
            row["price_basis"] = "adjusted"
            bars.append(row)
    bars = _validated_bars(bars, cutoff)
    if len(bars) < 61:
        raise RuntimeError("历史数据不足61个交易日")
    _cache[key] = (time.time(), bars)
    return bars

def _live_risk_bars(bars: list[dict]) -> list[dict]:
    latest = bars[-21:]
    if bars[-1].get("history_source") != "Yahoo" or bars[-1].get("price_basis") != "adjusted":
        return latest
    close, raw_close = number(bars[-1].get("close")), number(bars[-1].get("raw_close"))
    if close is None or raw_close is None or close <= 0 or raw_close <= 0:
        raise RuntimeError("保护价缺少有效历史原始价格锚点")
    scale = number(raw_close / close)
    if scale is None or scale <= 0:
        raise RuntimeError("保护价历史尺度无效")
    rebased = []
    for bar in latest:
        if bar.get("history_source") != "Yahoo" or bar.get("price_basis") != "adjusted":
            raise RuntimeError("保护价历史价格口径不一致")
        row = {**bar, "price_basis": "latest_raw_close_reference", "risk_rebase_factor": scale}
        # This is a price-unit conversion, not a verified split/share-count factor.
        row.pop("share_scale", None)
        for field in ("open", "high", "low", "close"):
            value = number(bar.get(field))
            row[field] = value * scale if value is not None else None
        rebased.append(row)
    return _validated_bars(rebased, bars[-1]["date"])


def enrich_foreign_history(rows: list[dict], *, as_of: str | None = None, limit: int = 120) -> list[dict]:
    # Candidate selection by turnover amount within one currency/market only.
    selected = sorted(rows, key=lambda row: number(row.get("amount")) or 0, reverse=True)[:limit]
    def enrich(row):
        row = {**row, "quote_as_of": as_of}
        try:
            bars = foreign_bars(row["ticker"], row["market"], as_of)
            closes = [bar["close"] for bar in bars]
            return {**row, **{f"change_{period}d": round((closes[-1] / closes[-period - 1] - 1) * 100, 2) for period in (5, 20, 60)}, "history_as_of": bars[-1]["date"], "risk_bars": _live_risk_bars(bars)}
        except Exception:
            clean_row = {key: value for key, value in row.items() if key not in {"risk_bars", "change_5d", "change_20d", "change_60d", "history_as_of"}}
            return {**clean_row, "history_error": "历史数据暂不可用，未填充趋势因子"}
    with ThreadPoolExecutor(max_workers=8) as executor:
        return list(executor.map(enrich, selected))
