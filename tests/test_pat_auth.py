from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from investment.api.routes import portfolio, tokens
from investment.data.pat_store import InMemoryPersonalAccessTokenStore


class FakeAuth0Verifier:
    def verify(self, token: str):
        from investment.api.auth import AuthenticatedUser

        if token != "valid-auth0-token":
            raise ValueError("invalid token")
        return AuthenticatedUser(sub="auth0|alice", email="alice@example.com")


class FakePortfolioService:
    def get_positions(self, user_id: str, include_history: bool = False):
        return {"positions": [], "storage": "fake", "owner": user_id}

    def save_positions(self, user_id: str, positions):
        return {"positions": positions, "storage": "fake", "owner": user_id}

    def analyze(self, user_id: str):
        return {"positions": [], "summary": "ok", "owner": user_id}


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(portfolio.router, prefix="/api")
    app.include_router(tokens.router, prefix="/api")
    return app


class PersonalAccessTokenAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryPersonalAccessTokenStore(
            now=lambda: datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc),
            secret_factory=lambda: "route-test-secret",
        )
        self.service = FakePortfolioService()
        self.patches = [
            patch("investment.api.auth.get_auth0_verifier", return_value=FakeAuth0Verifier()),
            patch("investment.api.auth.get_personal_access_token_store", return_value=self.store),
            patch.object(portfolio, "get_portfolio_service", return_value=self.service),
            patch.object(tokens, "get_personal_access_token_store", return_value=self.store),
        ]
        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)
        self.client = TestClient(make_app())

    def test_auth0_user_can_create_list_and_revoke_a_90_day_token(self) -> None:
        auth = {"Authorization": "Bearer valid-auth0-token"}

        created = self.client.post(
            "/api/portfolio/tokens",
            headers=auth,
            json={"name": "Codex MCP"},
        )

        self.assertEqual(created.status_code, 201)
        payload = created.json()["result"]
        self.assertEqual(payload["token"], "eai_pat_route-test-secret")
        self.assertEqual(payload["name"], "Codex MCP")
        self.assertEqual(payload["scopes"], ["portfolio:read"])
        self.assertNotIn("token_hash", payload)

        listed = self.client.get("/api/portfolio/tokens", headers=auth)
        self.assertEqual(listed.status_code, 200)
        listed_token = listed.json()["result"]["tokens"][0]
        self.assertNotIn("token", listed_token)
        self.assertNotIn("token_hash", listed_token)

        revoked = self.client.delete(
            f"/api/portfolio/tokens/{payload['id']}",
            headers=auth,
        )
        self.assertEqual(revoked.status_code, 200)
        self.assertTrue(revoked.json()["result"]["revoked"])

    def test_pat_can_read_and_analyze_but_cannot_write_or_manage_tokens(self) -> None:
        created = self.store.create("auth0|alice", "Remote")
        headers = {"Authorization": f"Bearer {created.token}"}

        positions = self.client.get("/api/portfolio/positions", headers=headers)
        analysis = self.client.post("/api/portfolio/analyze", headers=headers, json={})
        write = self.client.put(
            "/api/portfolio/positions",
            headers=headers,
            json={"positions": []},
        )
        manage = self.client.get("/api/portfolio/tokens", headers=headers)

        self.assertEqual(positions.status_code, 200)
        self.assertEqual(positions.json()["result"]["owner"], "auth0|alice")
        self.assertEqual(analysis.status_code, 200)
        self.assertEqual(write.status_code, 403)
        self.assertEqual(manage.status_code, 403)

    def test_verify_endpoint_exposes_only_identity_scope_and_expiry(self) -> None:
        created = self.store.create("auth0|alice", "Remote")

        response = self.client.get(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {created.token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()["result"]),
            {"sub", "scopes", "expires_at"},
        )
        self.assertEqual(response.json()["result"]["sub"], "auth0|alice")

    def test_revoked_pat_is_rejected(self) -> None:
        created = self.store.create("auth0|alice", "Remote")
        self.store.revoke("auth0|alice", created.record.id)

        response = self.client.get(
            "/api/portfolio/positions",
            headers={"Authorization": f"Bearer {created.token}"},
        )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
