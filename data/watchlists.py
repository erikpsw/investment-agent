"""Normalization, enrichment, and user-scoped watchlist operations."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional
from uuid import uuid4

from investment.data.research_snapshot import ResearchSnapshotService
from investment.data.watchlist_store import WatchlistStore, get_watchlist_store


class WatchlistGroupNotFound(LookupError):
    """Raised when a requested group does not exist for the user."""


def _market_for(ticker: str, market: Any) -> str:
    explicit = str(market or "").strip().upper()
    if explicit in {"CN", "HK", "US"}:
        return explicit
    value = ticker.lower()
    if value.startswith(("sh", "sz")) or value.isdigit():
        return "CN"
    if value.startswith("hk") or value.endswith(".hk"):
        return "HK"
    return "US"


class WatchlistService:
    def __init__(
        self,
        store: Optional[WatchlistStore] = None,
        research_service: Optional[ResearchSnapshotService] = None,
    ) -> None:
        self.store = store or get_watchlist_store()
        self.research_service = research_service or ResearchSnapshotService()

    def _normalize_groups(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []
        seen_group_ids: set[str] = set()
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("id") or uuid4()).strip()
            if not group_id or group_id in seen_group_ids:
                continue
            seen_group_ids.add(group_id)
            seen_tickers: set[str] = set()
            items: List[Dict[str, Any]] = []
            raw_items = group.get("items") if isinstance(group.get("items"), list) else []
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                ticker = str(raw.get("ticker") or "").strip()
                key = ticker.casefold()
                if not ticker or key in seen_tickers:
                    continue
                seen_tickers.add(key)
                items.append(
                    {
                        "ticker": ticker,
                        "name": str(raw.get("name") or "").strip(),
                        "market": _market_for(ticker, raw.get("market")),
                        "notes": str(raw.get("notes") or "").strip(),
                    }
                )
            normalized.append(
                {
                    "id": group_id,
                    "name": str(group.get("name") or "未命名分组").strip() or "未命名分组",
                    "items": items,
                }
            )
        return normalized

    def _enrich_groups(
        self,
        groups: List[Dict[str, Any]],
        include_history: bool,
    ) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []
        for group in groups:
            items = self.research_service.enrich(
                group.get("items", []), include_history=include_history
            ) if group.get("items") else []
            enriched.append({**group, "items": items})
        return enriched

    def get_watchlists(
        self,
        user_id: str,
        group_id: Optional[str] = None,
        include_history: bool = False,
    ) -> Dict[str, Any]:
        document = self.store.load(user_id)
        groups = self._normalize_groups(document.groups)
        if group_id:
            groups = [group for group in groups if group["id"] == group_id]
            if not groups:
                raise WatchlistGroupNotFound(group_id)
        return {
            "updated_at": document.updated_at,
            "storage": document.storage,
            "groups": self._enrich_groups(groups, include_history),
        }

    def save_watchlists(
        self,
        user_id: str,
        groups: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        normalized = self._normalize_groups(groups)
        document = self.store.save(user_id, normalized)
        return {
            "updated_at": document.updated_at,
            "storage": document.storage,
            "groups": self._enrich_groups(normalized, include_history=False),
        }


@lru_cache(maxsize=1)
def get_watchlist_service() -> WatchlistService:
    return WatchlistService()
