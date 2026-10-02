"""Revocable, hash-only personal access token persistence."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from threading import RLock
from typing import Any, Callable, Optional, Protocol


PAT_PREFIX = "eai_pat_"
PAT_LIFETIME = timedelta(days=90)
PAT_SCOPES = ("portfolio:read",)


class PersonalAccessTokenStorageError(RuntimeError):
    """Raised when PAT persistence is unavailable."""


@dataclass(frozen=True)
class PersonalAccessTokenRecord:
    id: str
    name: str
    token_prefix: str
    scopes: tuple[str, ...]
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


@dataclass(frozen=True)
class CreatedPersonalAccessToken:
    token: str
    record: PersonalAccessTokenRecord


@dataclass(frozen=True)
class PersonalAccessTokenIdentity:
    user_id: str
    scopes: tuple[str, ...]
    expires_at: datetime


class PersonalAccessTokenStore(Protocol):
    def create(self, user_id: str, name: str) -> CreatedPersonalAccessToken: ...

    def list_tokens(self, user_id: str) -> list[PersonalAccessTokenRecord]: ...

    def revoke(self, user_id: str, token_id: str) -> bool: ...

    def authenticate(self, token: str) -> Optional[PersonalAccessTokenIdentity]: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_user_id(user_id: str) -> str:
    value = str(user_id or "").strip()
    if not value:
        raise ValueError("user_id is required")
    return value


def _require_name(name: str) -> str:
    value = str(name or "").strip()
    if not value:
        raise ValueError("token name is required")
    if len(value) > 80:
        raise ValueError("token name must be at most 80 characters")
    return value


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        # PostgreSQL omits trailing fractional zeros; Python 3.10 requires
        # three or six digits when parsing an ISO fractional second.
        normalized = re.sub(r"\.(\d+)(?=Z|[+-]|$)",
            lambda match: "." + match.group(1)[:6].ljust(6, "0"), str(value))
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PersonalAccessTokenStorageError("PAT timestamps are invalid") from exc
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _record_from_row(row: dict[str, Any]) -> PersonalAccessTokenRecord:
    created_at = _parse_datetime(row.get("created_at"))
    expires_at = _parse_datetime(row.get("expires_at"))
    if created_at is None or expires_at is None:
        raise PersonalAccessTokenStorageError("PAT timestamps are invalid")
    return PersonalAccessTokenRecord(
        id=str(row.get("id") or ""),
        name=str(row.get("name") or ""),
        token_prefix=str(row.get("token_prefix") or ""),
        scopes=tuple(str(scope) for scope in (row.get("scopes") or PAT_SCOPES)),
        created_at=created_at,
        expires_at=expires_at,
        last_used_at=_parse_datetime(row.get("last_used_at")),
        revoked_at=_parse_datetime(row.get("revoked_at")),
    )


def _new_token(secret_factory: Callable[[], str]) -> tuple[str, str]:
    token = f"{PAT_PREFIX}{secret_factory()}"
    return token, token[:16]


class InMemoryPersonalAccessTokenStore:
    """Deterministic PAT store for tests and dependency injection."""

    def __init__(
        self,
        now: Callable[[], datetime] = _utc_now,
        secret_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        self._now = now
        self._secret_factory = secret_factory
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def create(self, user_id: str, name: str) -> CreatedPersonalAccessToken:
        owner = _require_user_id(user_id)
        label = _require_name(name)
        now = self._now()
        token, display_prefix = _new_token(self._secret_factory)
        row = {
            "id": str(uuid.uuid4()),
            "user_id": owner,
            "name": label,
            "token_prefix": display_prefix,
            "token_hash": _token_hash(token),
            "scopes": list(PAT_SCOPES),
            "created_at": now,
            "expires_at": now + PAT_LIFETIME,
            "last_used_at": None,
            "revoked_at": None,
        }
        with self._lock:
            self._records[row["id"]] = row
        return CreatedPersonalAccessToken(token=token, record=_record_from_row(row))

    def list_tokens(self, user_id: str) -> list[PersonalAccessTokenRecord]:
        owner = _require_user_id(user_id)
        with self._lock:
            rows = [dict(row) for row in self._records.values() if row["user_id"] == owner]
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        return [_record_from_row(row) for row in rows]

    def revoke(self, user_id: str, token_id: str) -> bool:
        owner = _require_user_id(user_id)
        with self._lock:
            row = self._records.get(str(token_id))
            if row is None or row["user_id"] != owner:
                return False
            if row["revoked_at"] is None:
                row["revoked_at"] = self._now()
            return True

    def authenticate(self, token: str) -> Optional[PersonalAccessTokenIdentity]:
        if not str(token).startswith(PAT_PREFIX):
            return None
        digest = _token_hash(token)
        with self._lock:
            row = next(
                (
                    item
                    for item in self._records.values()
                    if hmac.compare_digest(str(item["token_hash"]), digest)
                ),
                None,
            )
            if row is None:
                return None
            now = self._now()
            if row["revoked_at"] is not None or row["expires_at"] <= now:
                return None
            row["last_used_at"] = now
            return PersonalAccessTokenIdentity(
                user_id=str(row["user_id"]),
                scopes=tuple(row["scopes"]),
                expires_at=row["expires_at"],
            )


class SupabasePersonalAccessTokenStore:
    TABLE = "user_personal_access_tokens"

    def __init__(
        self,
        url: str,
        service_key: str,
        client: Any = None,
        now: Callable[[], datetime] = _utc_now,
        secret_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        if not url.strip() or not service_key.strip():
            raise PersonalAccessTokenStorageError("Supabase PAT storage is not configured")
        if client is None:
            from supabase import create_client

            client = create_client(url.strip(), service_key.strip())
        self._client = client
        self._now = now
        self._secret_factory = secret_factory

    def create(self, user_id: str, name: str) -> CreatedPersonalAccessToken:
        owner = _require_user_id(user_id)
        label = _require_name(name)
        now = self._now()
        token, display_prefix = _new_token(self._secret_factory)
        row = {
            "id": str(uuid.uuid4()),
            "user_id": owner,
            "name": label,
            "token_prefix": display_prefix,
            "token_hash": _token_hash(token),
            "scopes": list(PAT_SCOPES),
            "created_at": now.isoformat(),
            "expires_at": (now + PAT_LIFETIME).isoformat(),
        }
        try:
            response = self._client.table(self.TABLE).insert(row).execute()
        except Exception as exc:
            raise PersonalAccessTokenStorageError("Unable to create PAT") from exc
        rows = getattr(response, "data", None) or []
        persisted = rows[0] if isinstance(rows, list) and rows else row
        return CreatedPersonalAccessToken(token=token, record=_record_from_row(persisted))

    def list_tokens(self, user_id: str) -> list[PersonalAccessTokenRecord]:
        owner = _require_user_id(user_id)
        try:
            response = (
                self._client.table(self.TABLE)
                .select("id,name,token_prefix,scopes,created_at,expires_at,last_used_at,revoked_at")
                .eq("user_id", owner)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception as exc:
            raise PersonalAccessTokenStorageError("Unable to list PATs") from exc
        rows = getattr(response, "data", None) or []
        return [_record_from_row(row) for row in rows if isinstance(row, dict)]

    def revoke(self, user_id: str, token_id: str) -> bool:
        owner = _require_user_id(user_id)
        try:
            response = (
                self._client.table(self.TABLE)
                .update({"revoked_at": self._now().isoformat()})
                .eq("id", str(token_id))
                .eq("user_id", owner)
                .is_("revoked_at", "null")
                .execute()
            )
        except Exception as exc:
            raise PersonalAccessTokenStorageError("Unable to revoke PAT") from exc
        rows = getattr(response, "data", None) or []
        return bool(rows)

    def authenticate(self, token: str) -> Optional[PersonalAccessTokenIdentity]:
        if not str(token).startswith(PAT_PREFIX):
            return None
        digest = _token_hash(token)
        try:
            response = (
                self._client.table(self.TABLE)
                .select("id,user_id,token_hash,scopes,expires_at,revoked_at")
                .eq("token_hash", digest)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            raise PersonalAccessTokenStorageError("Unable to validate PAT") from exc
        rows = getattr(response, "data", None) or []
        row = rows[0] if isinstance(rows, list) and rows else None
        if not isinstance(row, dict) or not hmac.compare_digest(str(row.get("token_hash") or ""), digest):
            return None
        expires_at = _parse_datetime(row.get("expires_at"))
        now = self._now()
        if expires_at is None or expires_at <= now or row.get("revoked_at"):
            return None
        try:
            (
                self._client.table(self.TABLE)
                .update({"last_used_at": now.isoformat()})
                .eq("id", str(row.get("id")))
                .execute()
            )
        except Exception:
            pass
        return PersonalAccessTokenIdentity(
            user_id=str(row.get("user_id") or ""),
            scopes=tuple(str(scope) for scope in (row.get("scopes") or PAT_SCOPES)),
            expires_at=expires_at,
        )


@lru_cache(maxsize=1)
def get_personal_access_token_store() -> PersonalAccessTokenStore:
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    return SupabasePersonalAccessTokenStore(
        url=os.getenv("SUPABASE_URL", ""),
        service_key=service_key,
    )
