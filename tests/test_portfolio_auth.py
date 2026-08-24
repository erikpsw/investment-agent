from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from investment.api.auth import AuthenticatedUser, get_current_user
from investment.api.routes import portfolio
from investment.data.portfolio_store import PortfolioStorageError


class FakePortfolioService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_positions(self, user_id: str, include_history: bool = False):
        self.calls.append(("get", user_id, include_history))
        return {"positions": [], "storage": "fake"}

    def save_positions(self, user_id: str, positions):
        self.calls.append(("save", user_id))
        return {"positions": positions, "storage": "fake"}

    def apply_transaction(self, user_id: str, transaction):
        self.calls.append(("transaction", user_id, transaction["action"]))
        return {"positions": [], "transaction": transaction, "storage": "fake"}

    def analyze(self, user_id: str):
        self.calls.append(("analyze", user_id))
        return {"positions": [], "summary": "ok"}


def make_app(service: FakePortfolioService, authenticated: bool) -> FastAPI:
    app = FastAPI()
    app.include_router(portfolio.router, prefix="/api")
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            sub="auth0|user-123",
            email="investor@example.com",
        )
    app.state.portfolio_service = service
    return app


class PortfolioAuthTests(unittest.TestCase):
    def test_missing_bearer_token_is_rejected(self) -> None:
        service = FakePortfolioService()
        with patch.object(portfolio, "get_portfolio_service", return_value=service):
            response = TestClient(make_app(service, authenticated=False)).get(
                "/api/portfolio/positions"
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(service.calls, [])

    def test_all_handlers_use_authenticated_subject(self) -> None:
        service = FakePortfolioService()
        with patch.object(portfolio, "get_portfolio_service", return_value=service):
            client = TestClient(make_app(service, authenticated=True))
            get_response = client.get("/api/portfolio/positions")
            history_response = client.get("/api/portfolio/positions?include_history=true")
            put_response = client.put(
                "/api/portfolio/positions",
                json={
                    "positions": [
                        {
                            "ticker": "hk07709",
                            "name": "XL二南方海力士",
                            "market": "HK",
                            "quantity": 200,
                            "avg_cost": 102,
                            "notes": "",
                        }
                    ]
                },
            )
            analyze_response = client.post("/api/portfolio/analyze", json={})

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(analyze_response.status_code, 200)
        self.assertEqual(
            service.calls,
            [
                ("get", "auth0|user-123", False),
                ("get", "auth0|user-123", True),
                ("save", "auth0|user-123"),
                ("analyze", "auth0|user-123"),
            ],
        )

    def test_save_contract_does_not_accept_user_id(self) -> None:
        service = FakePortfolioService()
        with patch.object(portfolio, "get_portfolio_service", return_value=service):
            client = TestClient(make_app(service, authenticated=True))
            response = client.put(
                "/api/portfolio/positions",
                json={"user_id": "auth0|victim", "positions": []},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(service.calls, [])

    def test_transaction_uses_existing_authenticated_reader_token(self) -> None:
        service = FakePortfolioService()
        app = make_app(service, authenticated=False)
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            sub="auth0|user-123",
            auth_type="pat",
            scopes=("portfolio:read",),
        )
        with patch.object(portfolio, "get_portfolio_service", return_value=service):
            response = TestClient(app).post(
                "/api/portfolio/transactions",
                json={
                    "action": "buy",
                    "instrument_id": "AAPL",
                    "name": "Apple Inc.",
                    "market": "US",
                    "quantity": 2,
                    "price": 150,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.calls, [("transaction", "auth0|user-123", "buy")])

    def test_transaction_validation_error_is_returned_as_unprocessable(self) -> None:
        service = FakePortfolioService()
        service.apply_transaction = lambda user_id, transaction: (_ for _ in ()).throw(
            ValueError("insufficient USD cash")
        )
        with patch.object(portfolio, "get_portfolio_service", return_value=service):
            response = TestClient(make_app(service, authenticated=True)).post(
                "/api/portfolio/transactions",
                json={
                    "action": "buy",
                    "instrument_id": "AAPL",
                    "name": "Apple Inc.",
                    "market": "US",
                    "quantity": 2,
                    "price": 150,
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "insufficient USD cash")

    def test_cloud_storage_failure_returns_service_unavailable(self) -> None:
        service = FakePortfolioService()
        service.get_positions = lambda user_id, include_history=False: (_ for _ in ()).throw(
            PortfolioStorageError("secret internal storage error")
        )
        with patch.object(portfolio, "get_portfolio_service", return_value=service):
            response = TestClient(make_app(service, authenticated=True)).get(
                "/api/portfolio/positions"
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Portfolio storage is unavailable")


if __name__ == "__main__":
    unittest.main()
