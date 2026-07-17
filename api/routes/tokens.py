"""Personal access token management and bearer verification routes."""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from investment.api.auth import AuthenticatedUser, get_auth0_user, get_current_user
from investment.data.pat_store import (
    PersonalAccessTokenRecord,
    PersonalAccessTokenStorageError,
    get_personal_access_token_store,
)


router = APIRouter()


class CreatePersonalAccessTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Token name is required")
        return normalized


async def _run_store_call(call: Callable[..., Any], *args: Any) -> Any:
    try:
        return await asyncio.to_thread(call, *args)
    except PersonalAccessTokenStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Personal access token storage is unavailable",
        ) from exc


def _record_payload(record: PersonalAccessTokenRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "token_prefix": record.token_prefix,
        "scopes": list(record.scopes),
        "created_at": record.created_at,
        "expires_at": record.expires_at,
        "last_used_at": record.last_used_at,
        "revoked_at": record.revoked_at,
    }


@router.get("/auth/verify")
async def verify_bearer_token(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    return {
        "status": "ok",
        "result": {
            "sub": current_user.sub,
            "scopes": list(current_user.scopes),
            "expires_at": current_user.expires_at,
        },
    }


@router.get("/portfolio/tokens")
async def list_personal_access_tokens(
    current_user: AuthenticatedUser = Depends(get_auth0_user),
):
    records = await _run_store_call(
        get_personal_access_token_store().list_tokens,
        current_user.sub,
    )
    return {
        "status": "ok",
        "result": {"tokens": [_record_payload(record) for record in records]},
    }


@router.post("/portfolio/tokens", status_code=status.HTTP_201_CREATED)
async def create_personal_access_token(
    request: CreatePersonalAccessTokenRequest,
    current_user: AuthenticatedUser = Depends(get_auth0_user),
):
    created = await _run_store_call(
        get_personal_access_token_store().create,
        current_user.sub,
        request.name,
    )
    return {
        "status": "ok",
        "result": {"token": created.token, **_record_payload(created.record)},
    }


@router.delete("/portfolio/tokens/{token_id}")
async def revoke_personal_access_token(
    token_id: str,
    current_user: AuthenticatedUser = Depends(get_auth0_user),
):
    revoked = await _run_store_call(
        get_personal_access_token_store().revoke,
        current_user.sub,
        token_id,
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Personal access token not found")
    return {"status": "ok", "result": {"revoked": True}}
