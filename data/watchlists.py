"""Normalization, enrichment, and user-scoped watchlist operations."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional
from uuid import uuid4

from investment.data.research_snapshot import ResearchSnapshotService
from investment.data.watchlist_store import WatchlistStore, get_watchlist_store


class WatchlistGroupNotFound(LookupError):
    """Raised when a requested group does not exist for the user."""


class WatchlistItemNotFound(LookupError):
    """Raised when a requested item does not exist in a watchlist group."""


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
                    "parent_id": str(group.get("parent_id") or group.get("parentId") or "").strip() or None,
                    "items": items,
                }
            )
        return normalized

    def _tree(self, groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_id = {group["id"]: {**group, "children": []} for group in groups}
        roots: List[Dict[str, Any]] = []
        for group in by_id.values():
            parent = by_id.get(group.get("parent_id"))
            if parent is not None and parent["id"] != group["id"]:
                parent["children"].append(group)
            else:
                group["parent_id"] = None
                roots.append(group)
        return roots

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
            enriched.append({**group, "items": items, "children": self._enrich_groups(group.get("children", []), include_history)})
        return enriched

    def _document_groups(self, user_id: str) -> List[Dict[str, Any]]:
        return self._normalize_groups(self.store.load(user_id).groups)

    def _save_and_result(self, user_id: str, groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        document = self.store.save(user_id, groups)
        return {"updated_at": document.updated_at, "storage": document.storage, "groups": self._enrich_groups(self._tree(groups), False)}

    @staticmethod
    def _group(groups: List[Dict[str, Any]], group_id: str) -> Dict[str, Any]:
        for group in groups:
            if group["id"] == group_id:
                return group
        raise WatchlistGroupNotFound(group_id)

    @staticmethod
    def _assert_parent(groups: List[Dict[str, Any]], group_id: str, parent_id: Optional[str]) -> None:
        if parent_id is None:
            return
        if parent_id == group_id:
            raise ValueError("A group cannot be its own parent")
        parent = next((group for group in groups if group["id"] == parent_id), None)
        if parent is None:
            raise WatchlistGroupNotFound(parent_id)
        current = parent
        while current:
            if current["id"] == group_id:
                raise ValueError("A group cannot be moved into its descendant")
            current = next((group for group in groups if group["id"] == current.get("parent_id")), None)

    def create_group(self, user_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        groups = self._document_groups(user_id)
        group_id = str(payload.get("id") or uuid4()).strip()
        if not group_id or any(group["id"] == group_id for group in groups):
            raise ValueError("Watchlist group id already exists or is invalid")
        parent_id = str(payload.get("parent_id") or "").strip() or None
        self._assert_parent(groups, group_id, parent_id)
        groups.append({"id": group_id, "name": str(payload.get("name") or "").strip() or "未命名分组", "parent_id": parent_id, "items": []})
        return self._save_and_result(user_id, groups)

    def update_group(self, user_id: str, group_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        groups = self._document_groups(user_id)
        group = self._group(groups, group_id)
        if "name" in payload:
            name = str(payload["name"] or "").strip()
            if not name:
                raise ValueError("Watchlist group name is required")
            group["name"] = name
        if "parent_id" in payload:
            parent_id = str(payload["parent_id"] or "").strip() or None
            self._assert_parent(groups, group_id, parent_id)
            group["parent_id"] = parent_id
        return self._save_and_result(user_id, groups)

    def delete_group(self, user_id: str, group_id: str) -> Dict[str, Any]:
        groups = self._document_groups(user_id)
        self._group(groups, group_id)
        deleted = {group_id}
        changed = True
        while changed:
            changed = False
            for group in groups:
                if group.get("parent_id") in deleted and group["id"] not in deleted:
                    deleted.add(group["id"])
                    changed = True
        return self._save_and_result(user_id, [group for group in groups if group["id"] not in deleted])

    def add_item(self, user_id: str, group_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        groups = self._document_groups(user_id)
        group = self._group(groups, group_id)
        ticker = str(payload.get("ticker") or "").strip()
        if not ticker:
            raise ValueError("Ticker is required")
        if any(str(item["ticker"]).casefold() == ticker.casefold() for item in group["items"]):
            raise ValueError("Ticker already exists in this group")
        group["items"].append({"ticker": ticker, "name": str(payload.get("name") or "").strip(), "market": _market_for(ticker, payload.get("market")), "notes": str(payload.get("notes") or "").strip()})
        return self._save_and_result(user_id, groups)

    def update_item(self, user_id: str, group_id: str, ticker: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        groups = self._document_groups(user_id)
        source = self._group(groups, group_id)
        item = next((entry for entry in source["items"] if str(entry["ticker"]).casefold() == ticker.casefold()), None)
        if item is None:
            raise WatchlistItemNotFound(ticker)
        target_id = str(payload.get("target_group_id") or group_id).strip()
        target = self._group(groups, target_id)
        if target is not source:
            if any(str(entry["ticker"]).casefold() == ticker.casefold() for entry in target["items"]):
                raise ValueError("Ticker already exists in the target group")
            source["items"].remove(item)
            target["items"].append(item)
        for field in ("name", "market", "notes"):
            if field in payload:
                item[field] = _market_for(item["ticker"], payload[field]) if field == "market" else str(payload[field] or "").strip()
        return self._save_and_result(user_id, groups)

    def delete_item(self, user_id: str, group_id: str, ticker: str) -> Dict[str, Any]:
        groups = self._document_groups(user_id)
        group = self._group(groups, group_id)
        filtered = [item for item in group["items"] if str(item["ticker"]).casefold() != ticker.casefold()]
        if len(filtered) == len(group["items"]):
            raise WatchlistItemNotFound(ticker)
        group["items"] = filtered
        return self._save_and_result(user_id, groups)

    def get_watchlists(
        self,
        user_id: str,
        group_id: Optional[str] = None,
        include_history: bool = False,
    ) -> Dict[str, Any]:
        document = self.store.load(user_id)
        groups = self._normalize_groups(document.groups)
        if group_id:
            selected = [group for group in groups if group["id"] == group_id]
            if not selected:
                raise WatchlistGroupNotFound(group_id)
            groups = selected
        return {
            "updated_at": document.updated_at,
            "storage": document.storage,
            "groups": self._enrich_groups(self._tree(groups), include_history),
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
            "groups": self._enrich_groups(self._tree(normalized), include_history=False),
        }


@lru_cache(maxsize=1)
def get_watchlist_service() -> WatchlistService:
    return WatchlistService()
