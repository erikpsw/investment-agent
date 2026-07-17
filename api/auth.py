"""Auth0 access-token validation for protected FastAPI routes."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Callable, Optional

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from investment.data.pat_store import (
    PAT_PREFIX,
    PersonalAccessTokenStorageError,
    get_personal_access_token_store,
)


_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    sub: str
    email: Optional[str] = None
    auth_type: str = "auth0"
    scopes: tuple[str, ...] = ("portfolio:read", "portfolio:write", "tokens:manage")
    expires_at: Optional[datetime] = None


class Auth0TokenVerifier:
    def __init__(self, domain: str, audience: str) -> None:
        normalized_domain = domain.strip().rstrip("/")
        if normalized_domain.startswith("https://"):
            normalized_domain = normalized_domain[len("https://") :]
        elif normalized_domain.startswith("http://"):
            normalized_domain = normalized_domain[len("http://") :]
        if not normalized_domain:
            raise ValueError("Auth0 domain is required")

        self.issuer = f"https://{normalized_domain}/"
        self.audience = audience.strip()
        self.jwks_client = (
            jwt.PyJWKClient(f"{self.issuer}.well-known/jwks.json")
            if self.audience
            else None
        )
        self.userinfo_get = requests.get

    def verify(self, token: str) -> AuthenticatedUser:
        if self.audience:
            if self.jwks_client is None:
                raise RuntimeError("Auth0 JWKS client is unavailable")
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        else:
            response = self.userinfo_get(
                f"{self.issuer}userinfo",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            response.raise_for_status()
            claims = response.json()
            if not isinstance(claims, dict):
                raise ValueError("Auth0 userinfo response is invalid")
        subject = str(claims.get("sub") or "").strip()
        if not subject:
            raise jwt.InvalidTokenError("Token is missing sub")
        email = claims.get("email")
        return AuthenticatedUser(
            sub=subject,
            email=str(email).strip() if email else None,
        )


@lru_cache(maxsize=1)
def get_auth0_verifier() -> Auth0TokenVerifier:
    domain = os.getenv("AUTH0_DOMAIN", "")
    audience = os.getenv("AUTH0_AUDIENCE", "")
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth0 is not configured",
        )
    return Auth0TokenVerifier(domain=domain, audience=audience)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        if token.startswith(PAT_PREFIX):
            identity = get_personal_access_token_store().authenticate(token)
            if identity is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid, expired, or revoked personal access token",
                    headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
                )
            return AuthenticatedUser(
                sub=identity.user_id,
                auth_type="pat",
                scopes=identity.scopes,
                expires_at=identity.expires_at,
            )
        return get_auth0_verifier().verify(token)
    except HTTPException:
        raise
    except PersonalAccessTokenStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Personal access token validation is unavailable",
        ) from exc
    except Exception as exc:
        if isinstance(exc, jwt.PyJWTError) or exc.__class__.__module__.startswith("jwt"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to validate access token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc


def get_auth0_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if current_user.auth_type != "auth0":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An interactive Auth0 session is required",
        )
    return current_user


def require_scope(scope: str) -> Callable[..., AuthenticatedUser]:
    def dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if scope not in current_user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required scope is missing: {scope}",
            )
        return current_user

    return dependency
