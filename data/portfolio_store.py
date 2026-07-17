"""User-scoped persistence for portfolio documents."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from threading import RLock
from typing import Any, Dict, List, Optional, Protocol


class PortfolioStorageError(RuntimeError):
    """Raised when cloud portfolio persistence is unavailable."""


@dataclass(frozen=True)
class PortfolioDocument:
    positions: List[Dict[str, Any]]
    updated_at: Optional[str]
    storage: str


class PortfolioStore(Protocol):
    def load(self, user_id: str) -> PortfolioDocument: ...

    def save(self, user_id: str, positions: List[Dict[str, Any]]) -> PortfolioDocument: ...


def _require_user_id(user_id: str) -> str:
    value = str(user_id or "").strip()
    if not value:
        raise ValueError("user_id is required")
    return value


class InMemoryPortfolioStore:
    """Deterministic store used by tests and explicit dependency injection."""

    def __init__(self) -> None:
        self._documents: Dict[str, PortfolioDocument] = {}
        self._lock = RLock()

    def load(self, user_id: str) -> PortfolioDocument:
        owner = _require_user_id(user_id)
        with self._lock:
            document = self._documents.get(owner)
            if document is None:
                return PortfolioDocument(positions=[], updated_at=None, storage="memory")
            return PortfolioDocument(
                positions=[dict(item) for item in document.positions],
                updated_at=document.updated_at,
                storage=document.storage,
            )

    def save(self, user_id: str, positions: List[Dict[str, Any]]) -> PortfolioDocument:
        owner = _require_user_id(user_id)
        document = PortfolioDocument(
            positions=[dict(item) for item in positions],
            updated_at=datetime.now(timezone.utc).isoformat(),
            storage="memory",
        )
        with self._lock:
            self._documents[owner] = document
        return self.load(owner)


class SupabasePortfolioStore:
    TABLE = "user_portfolios"

    def __init__(self, url: str, service_key: str, client: Any = None) -> None:
        if not url.strip() or not service_key.strip():
            raise PortfolioStorageError("Supabase cloud portfolio storage is not configured")
        if client is None:
            from supabase import create_client

            client = create_client(url.strip(), service_key.strip())
        self._client = client

    def load(self, user_id: str) -> PortfolioDocument:
        owner = _require_user_id(user_id)
        try:
            response = (
                self._client.table(self.TABLE)
                .select("positions,updated_at")
                .eq("user_id", owner)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise PortfolioStorageError("Unable to load portfolio from Supabase") from exc

        rows = getattr(response, "data", None) or []
        row = rows[0] if isinstance(rows, list) and rows else rows if isinstance(rows, dict) else None
        if not isinstance(row, dict):
            return PortfolioDocument(positions=[], updated_at=None, storage="supabase")
        positions = row.get("positions")
        return PortfolioDocument(
            positions=[dict(item) for item in positions if isinstance(item, dict)]
            if isinstance(positions, list)
            else [],
            updated_at=str(row.get("updated_at")) if row.get("updated_at") else None,
            storage="supabase",
        )

    def save(self, user_id: str, positions: List[Dict[str, Any]]) -> PortfolioDocument:
        owner = _require_user_id(user_id)
        updated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "user_id": owner,
            "positions": [dict(item) for item in positions],
            "updated_at": updated_at,
        }
        try:
            response = (
                self._client.table(self.TABLE)
                .upsert(payload, on_conflict="user_id")
                .execute()
            )
        except Exception as exc:
            raise PortfolioStorageError("Unable to save portfolio to Supabase") from exc

        rows = getattr(response, "data", None) or []
        row = rows[0] if isinstance(rows, list) and rows else payload
        return PortfolioDocument(
            positions=[dict(item) for item in row.get("positions", positions)],
            updated_at=str(row.get("updated_at") or updated_at),
            storage="supabase",
        )


@lru_cache(maxsize=1)
def get_portfolio_store() -> PortfolioStore:
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    return SupabasePortfolioStore(
        url=os.getenv("SUPABASE_URL", ""),
        service_key=service_key,
    )
