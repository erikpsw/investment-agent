"""User-scoped persistence for grouped watchlist documents."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from threading import RLock
from typing import Any, Dict, List, Optional, Protocol


class WatchlistStorageError(RuntimeError):
    """Raised when cloud watchlist persistence is unavailable."""


@dataclass(frozen=True)
class WatchlistDocument:
    groups: List[Dict[str, Any]]
    updated_at: Optional[str]
    storage: str


class WatchlistStore(Protocol):
    def load(self, user_id: str) -> WatchlistDocument: ...

    def save(self, user_id: str, groups: List[Dict[str, Any]]) -> WatchlistDocument: ...


def _owner(user_id: str) -> str:
    value = str(user_id or "").strip()
    if not value:
        raise ValueError("user_id is required")
    return value


def _copy_groups(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            **dict(group),
            "items": [dict(item) for item in group.get("items", []) if isinstance(item, dict)],
        }
        for group in groups
        if isinstance(group, dict)
    ]


class InMemoryWatchlistStore:
    def __init__(self) -> None:
        self._documents: Dict[str, WatchlistDocument] = {}
        self._lock = RLock()

    def load(self, user_id: str) -> WatchlistDocument:
        owner = _owner(user_id)
        with self._lock:
            document = self._documents.get(owner)
            if document is None:
                return WatchlistDocument(groups=[], updated_at=None, storage="memory")
            return WatchlistDocument(
                groups=_copy_groups(document.groups),
                updated_at=document.updated_at,
                storage=document.storage,
            )

    def save(self, user_id: str, groups: List[Dict[str, Any]]) -> WatchlistDocument:
        owner = _owner(user_id)
        with self._lock:
            self._documents[owner] = WatchlistDocument(
                groups=_copy_groups(groups),
                updated_at=datetime.now(timezone.utc).isoformat(),
                storage="memory",
            )
        return self.load(owner)


class SupabaseWatchlistStore:
    TABLE = "user_watchlists"

    def __init__(self, url: str, service_key: str, client: Any = None) -> None:
        if not url.strip() or not service_key.strip():
            raise WatchlistStorageError("Supabase cloud watchlist storage is not configured")
        if client is None:
            from supabase import create_client

            client = create_client(url.strip(), service_key.strip())
        self._client = client

    def load(self, user_id: str) -> WatchlistDocument:
        owner = _owner(user_id)
        try:
            response = (
                self._client.table(self.TABLE)
                .select("groups,updated_at")
                .eq("user_id", owner)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise WatchlistStorageError("Unable to load watchlists from Supabase") from exc
        rows = getattr(response, "data", None) or []
        row = rows[0] if isinstance(rows, list) and rows else rows if isinstance(rows, dict) else None
        if not isinstance(row, dict):
            return WatchlistDocument(groups=[], updated_at=None, storage="supabase")
        groups = row.get("groups")
        return WatchlistDocument(
            groups=_copy_groups(groups) if isinstance(groups, list) else [],
            updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
            storage="supabase",
        )

    def save(self, user_id: str, groups: List[Dict[str, Any]]) -> WatchlistDocument:
        owner = _owner(user_id)
        updated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "user_id": owner,
            "groups": _copy_groups(groups),
            "updated_at": updated_at,
        }
        try:
            response = (
                self._client.table(self.TABLE)
                .upsert(payload, on_conflict="user_id")
                .execute()
            )
        except Exception as exc:
            raise WatchlistStorageError("Unable to save watchlists to Supabase") from exc
        rows = getattr(response, "data", None) or []
        row = rows[0] if isinstance(rows, list) and rows else payload
        return WatchlistDocument(
            groups=_copy_groups(row.get("groups", payload["groups"])),
            updated_at=str(row.get("updated_at") or updated_at),
            storage="supabase",
        )


@lru_cache(maxsize=1)
def get_watchlist_store() -> WatchlistStore:
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    return SupabaseWatchlistStore(
        url=os.getenv("SUPABASE_URL", ""),
        service_key=service_key,
    )
