"""Market-data cache policies shared by watchlist quote and research requests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import time
from threading import RLock
from typing import Any, Dict, Iterable, Optional, Protocol, Tuple
from zoneinfo import ZoneInfo


_MARKET_TIMEZONES = {
    "CN": ZoneInfo("Asia/Shanghai"),
    "HK": ZoneInfo("Asia/Shanghai"),
    "US": ZoneInfo("America/New_York"),
}


def _local_time(market: str, moment: datetime) -> datetime:
    timezone = _MARKET_TIMEZONES.get(market.upper(), _MARKET_TIMEZONES["US"])
    return moment.replace(tzinfo=timezone) if moment.tzinfo is None else moment.astimezone(timezone)


def is_market_open(market: str, moment: Optional[datetime] = None) -> bool:
    """Return whether a regular trading session is active for a market.

    The schedule deliberately treats weekends as closed. Exchange holidays are
    naturally served from the last successful cache entry rather than causing a
    burst of repeated upstream calls.
    """
    local = _local_time(market, moment or datetime.now(timezone.utc))
    if local.weekday() >= 5:
        return False
    clock = local.timetz().replace(tzinfo=None)
    normalized = market.upper()
    if normalized == "CN":
        return (clock.hour, clock.minute) >= (9, 30) and (clock.hour, clock.minute) < (11, 30) or (clock.hour, clock.minute) >= (13, 0) and (clock.hour, clock.minute) < (15, 0)
    if normalized == "HK":
        return (clock.hour, clock.minute) >= (9, 30) and (clock.hour, clock.minute) < (12, 0) or (clock.hour, clock.minute) >= (13, 0) and (clock.hour, clock.minute) < (16, 0)
    return (clock.hour, clock.minute) >= (9, 30) and (clock.hour, clock.minute) < (16, 0)


@dataclass(frozen=True)
class _CacheEntry:
    value: Dict[str, Any]
    fetched_at: datetime


class MarketCacheStore(Protocol):
    def load(self, keys: Iterable[Tuple[str, str, str]]) -> Dict[Tuple[str, str, str], Tuple[Dict[str, Any], datetime]]: ...
    def save(self, key: Tuple[str, str, str], value: Dict[str, Any], fetched_at: datetime) -> None: ...


class SupabaseMarketCacheStore:
    """Small durable L2 cache for Vercel instances; failures are best-effort."""
    TABLE = "market_data_cache"

    def __init__(self, url: str, key: str) -> None:
        from supabase import create_client
        self.client = create_client(url, key)
        self._retry_after = 0.0

    @staticmethod
    def _cache_key(key: Tuple[str, str, str]) -> str:
        return ":".join(key)

    def load(self, keys: Iterable[Tuple[str, str, str]]) -> Dict[Tuple[str, str, str], Tuple[Dict[str, Any], datetime]]:
        requested = list(keys)
        if not requested or time.monotonic() < self._retry_after:
            return {}
        try:
            response = self.client.table(self.TABLE).select("cache_key,payload,fetched_at").in_("cache_key", [self._cache_key(key) for key in requested]).execute()
            result: Dict[Tuple[str, str, str], Tuple[Dict[str, Any], datetime]] = {}
            for row in response.data or []:
                parts = str(row.get("cache_key") or "").split(":", 2)
                payload = row.get("payload")
                fetched_at = row.get("fetched_at")
                if len(parts) == 3 and isinstance(payload, dict) and fetched_at:
                    result[(parts[0], parts[1], parts[2])] = (payload, datetime.fromisoformat(str(fetched_at).replace("Z", "+00:00")))
            return result
        except Exception:
            self._retry_after = time.monotonic() + 60
            return {}

    def save(self, key: Tuple[str, str, str], value: Dict[str, Any], fetched_at: datetime) -> None:
        self.save_many([(key, value, fetched_at)])

    def save_many(self, entries) -> None:
        if time.monotonic() < self._retry_after:
            return
        try:
            rows = [{"cache_key": self._cache_key(key), "market": key[0], "ticker": key[1], "kind": key[2], "payload": value, "fetched_at": fetched_at.astimezone().isoformat() if fetched_at.tzinfo else fetched_at.isoformat()} for key, value, fetched_at in entries]
            if rows:
                self.client.table(self.TABLE).upsert(rows, on_conflict="cache_key").execute()
        except Exception:
            self._retry_after = time.monotonic() + 60


class MarketDataCache:
    """Thread-safe L1 cache with market-aware freshness rules.

    During a session quotes are fresh for a small TTL. Outside a session the
    last valid close remains usable, so opening a watchlist at night does not
    call a quote provider again.
    """
    def __init__(self, quote_ttl_seconds: int = 15, store: Optional[MarketCacheStore] = None) -> None:
        self.quote_ttl = timedelta(seconds=quote_ttl_seconds)
        self._entries: Dict[Tuple[str, str, str], _CacheEntry] = {}
        self._lock = RLock()
        self._store = store

    @staticmethod
    def _key(market: str, ticker: str, kind: str) -> Tuple[str, str, str]:
        return market.upper(), ticker.strip().upper(), "quote-v2" if kind == "quote" else kind

    def get(
        self,
        market: str,
        ticker: str,
        kind: str,
        now: Optional[datetime] = None,
    ) -> Optional[Dict[str, Any]]:
        timestamp = now or datetime.now(timezone.utc)
        key = self._key(market, ticker, kind)
        with self._lock:
            entry = self._entries.get(key)
        if entry is None and self._store is not None:
            persisted = self._store.load([key]).get(key)
            if persisted is not None:
                entry = _CacheEntry(value=dict(persisted[0]), fetched_at=persisted[1])
                with self._lock:
                    self._entries[key] = entry
        return self._read_entry(market, kind, timestamp, entry)

    def _read_entry(
        self,
        market: str,
        kind: str,
        timestamp: datetime,
        entry: Optional[_CacheEntry],
    ) -> Optional[Dict[str, Any]]:
        if entry is None:
            return None
        local_now = _local_time(market, timestamp)
        fetched_at = _local_time(market, entry.fetched_at)
        age = local_now - fetched_at
        if age < timedelta(0):
            return None
        if kind != "quote":
            ttl = timedelta(minutes=5) if is_market_open(market, timestamp) else timedelta(hours=6)
            return dict(entry.value) if age <= ttl else None
        if is_market_open(market, timestamp):
            return dict(entry.value) if age <= self.quote_ttl else None
        # Keep a close over nights/weekends, but expire it after a new session.
        session_day = local_now.date()
        if local_now.hour < 9 or (local_now.hour == 9 and local_now.minute < 30):
            session_day -= timedelta(days=1)
        while session_day.weekday() >= 5:
            session_day -= timedelta(days=1)
        if fetched_at.date() < session_day:
            return None
        return dict(entry.value)

    def get_many(
        self,
        entries: Iterable[Tuple[str, str]],
        kind: str,
        now: Optional[datetime] = None,
    ) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Read many cache entries with at most one durable-store request."""
        timestamp = now or datetime.now(timezone.utc)
        requested = [(str(market), str(ticker)) for market, ticker in entries]
        results: Dict[Tuple[str, str], Dict[str, Any]] = {}
        missing: list[Tuple[str, str, str]] = []
        for market, ticker in requested:
            key = (market.upper(), ticker.upper())
            with self._lock:
                entry = self._entries.get(self._key(market, ticker, kind))
            cached = self._read_entry(market, kind, timestamp, entry)
            if cached is None:
                missing.append(self._key(market, ticker, kind))
            else:
                results[key] = cached
        if missing and self._store is not None:
            for key, (value, fetched_at) in self._store.load(missing).items():
                with self._lock:
                    self._entries[key] = _CacheEntry(value=dict(value), fetched_at=fetched_at)
            for market, ticker in requested:
                key = (market.upper(), ticker.upper())
                if key not in results:
                    with self._lock:
                        entry = self._entries.get(self._key(market, ticker, kind))
                    cached = self._read_entry(market, kind, timestamp, entry)
                    if cached is not None:
                        results[key] = cached
        return results

    def set_many(self, entries, kind: str, now: Optional[datetime] = None) -> None:
        fetched_at = now or datetime.now(timezone.utc)
        rows = [(self._key(market, ticker, kind), dict(value), fetched_at) for market, ticker, value in entries]
        with self._lock:
            for key, value, timestamp in rows:
                self._entries[key] = _CacheEntry(value=value, fetched_at=timestamp)
        if self._store is not None:
            batch_save = getattr(self._store, "save_many", None)
            if batch_save is not None:
                batch_save(rows)
            else:
                for key, value, timestamp in rows:
                    self._store.save(key, value, timestamp)

    def set(
        self,
        market: str,
        ticker: str,
        kind: str,
        value: Dict[str, Any],
        now: Optional[datetime] = None,
    ) -> None:
        key = self._key(market, ticker, kind)
        fetched_at = now or datetime.now(timezone.utc)
        with self._lock:
            self._entries[key] = _CacheEntry(value=dict(value), fetched_at=fetched_at)
        if self._store is not None:
            self._store.save(key, dict(value), fetched_at)


def get_market_data_cache() -> MarketDataCache:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if url and key:
        try:
            return MarketDataCache(store=SupabaseMarketCacheStore(url, key))
        except Exception:
            pass
    return MarketDataCache()
