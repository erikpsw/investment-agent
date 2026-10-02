from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from investment.api.auth import AuthenticatedUser, get_current_user
from investment.api.routes import watchlists
from investment.data.watchlist_store import WatchlistStorageError
from investment.data.watchlists import WatchlistGroupNotFound


class FakeWatchlistService:
    def __init__(self) -> None:
        self.calls = []

    def get_watchlists(self, user_id, group_id=None, include_history=False, include_research=True, quotes_only=False, include_quotes=True):
        self.calls.append(("get", user_id, group_id, include_history, include_research, quotes_only, include_quotes))

        return {"groups": [], "storage": "fake"}

    def save_watchlists(self, user_id, groups):
        self.calls.append(("save", user_id, groups))
        return {"groups": groups, "storage": "fake"}

    def create_group(self, user_id, group):
        self.calls.append(("create_group", user_id, group))
        return {"groups": [], "storage": "fake"}

    def add_item(self, user_id, group_id, item):
        self.calls.append(("add_item", user_id, group_id, item))
        return {"groups": [], "storage": "fake"}

    def batch(self, user_id, operations):
        self.calls.append(("batch", user_id, operations))
        return {"summary": {"total": len(operations)}, "results": []}

    def get_item_research(self, user_id, group_id, ticker):
        self.calls.append(("research", user_id, group_id, ticker))
        return {"quote": {"price": 100}}

    def get_research(self, user_id, tickers):
        self.calls.append(("research", user_id, tickers))
        return {"items": []}



def make_app(service: FakeWatchlistService, user: AuthenticatedUser | None) -> FastAPI:
    app = FastAPI()
    app.include_router(watchlists.router, prefix="/api")
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


def test_missing_token_is_rejected_before_service_call() -> None:
    service = FakeWatchlistService()
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(make_app(service, None)).get("/api/watchlists")

    assert response.status_code == 401
    assert service.calls == []


def test_get_forwards_authenticated_subject_filter_and_history() -> None:
    service = FakeWatchlistService()
    user = AuthenticatedUser(sub="auth0|alice")
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(make_app(service, user)).get(
            "/api/watchlists?group_id=core&include_history=true&include_quotes=false"
        )

    assert response.status_code == 200
    assert service.calls == [("get", "auth0|alice", "core", True, True, False, False)]


def test_lightweight_request_disables_research_enrichment() -> None:
    service = FakeWatchlistService()
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(make_app(service, AuthenticatedUser(sub="auth0|alice"))).get(
            "/api/watchlists?include_research=false"
        )
    assert response.status_code == 200
    assert service.calls == [("get", "auth0|alice", None, False, False, False, True)]


def test_item_research_only_reads_selected_instrument() -> None:
    service = FakeWatchlistService()
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(make_app(service, AuthenticatedUser(sub="auth0|alice"))).get(
            "/api/watchlists/groups/core/items/AAPL/research"
        )
    assert response.status_code == 200
    assert service.calls == [("research", "auth0|alice", "core", "AAPL")]



def test_put_uses_subject_and_rejects_client_user_id() -> None:
    service = FakeWatchlistService()
    user = AuthenticatedUser(sub="auth0|alice")
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        client = TestClient(make_app(service, user))
        saved = client.put(
            "/api/watchlists",
            json={
                "groups": [
                    {
                        "id": "core",
                        "name": "Core",
                        "items": [
                            {"ticker": "AAPL", "name": "Apple", "market": "US", "notes": ""}
                        ],
                    }
                ]
            },
        )
        injected = client.put(
            "/api/watchlists",
            json={"user_id": "auth0|victim", "groups": []},
        )

    assert saved.status_code == 200
    assert service.calls[0][0:2] == ("save", "auth0|alice")
    assert injected.status_code == 422


def test_read_only_pat_cannot_write() -> None:
    service = FakeWatchlistService()
    user = AuthenticatedUser(
        sub="auth0|alice",
        auth_type="pat",
        scopes=("portfolio:read",),
    )
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(make_app(service, user)).put(
            "/api/watchlists", json={"groups": []}
        )

    assert response.status_code == 403
    assert service.calls == []


def test_unknown_group_returns_not_found() -> None:
    service = FakeWatchlistService()
    service.get_watchlists = lambda user_id, group_id=None, include_history=False, include_research=True, quotes_only=False, include_quotes=True: (_ for _ in ()).throw(

        WatchlistGroupNotFound(group_id)
    )
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(
            make_app(service, AuthenticatedUser(sub="auth0|alice"))
        ).get("/api/watchlists?group_id=missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Watchlist group was not found"


def test_storage_failure_returns_service_unavailable() -> None:
    service = FakeWatchlistService()
    service.get_watchlists = lambda user_id, group_id=None, include_history=False, include_research=True, quotes_only=False, include_quotes=True: (_ for _ in ()).throw(

        WatchlistStorageError("secret storage detail")
    )
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(
            make_app(service, AuthenticatedUser(sub="auth0|alice"))
        ).get("/api/watchlists")

    assert response.status_code == 503
    assert response.json()["detail"] == "Watchlist storage is unavailable"


def test_group_and_item_mutations_use_the_authenticated_subject() -> None:
    service = FakeWatchlistService()
    user = AuthenticatedUser(sub="auth0|alice")
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        client = TestClient(make_app(service, user))
        group = client.post("/api/watchlists/groups", json={"id": "us", "name": "美国"})
        item = client.post("/api/watchlists/groups/us/items", json={"ticker": "AAPL"})

    assert group.status_code == 200
    assert item.status_code == 200
    assert service.calls == [
        ("create_group", "auth0|alice", {"id": "us", "name": "美国", "parent_id": None}),
        ("add_item", "auth0|alice", "us", {"ticker": "AAPL", "name": "", "market": "", "notes": ""}),
    ]


def test_batch_forwards_all_operations_in_one_authenticated_call() -> None:
    service = FakeWatchlistService()
    user = AuthenticatedUser(sub="auth0|alice")
    operations = [
        {"action": "create", "resource": "item", "group_id": "core", "ticker": "AAPL"},
        {"action": "delete", "resource": "item", "group_id": "core", "ticker": "MSFT"},
    ]
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(make_app(service, user)).post(
            "/api/watchlists/batch", json={"operations": operations}
        )

    assert response.status_code == 200
    assert service.calls == [("batch", "auth0|alice", operations)]


def test_research_prefetch_is_authenticated_and_scoped_to_the_user() -> None:
    service = FakeWatchlistService()
    user = AuthenticatedUser(sub="auth0|alice")
    with patch.object(watchlists, "get_watchlist_service", return_value=service):
        response = TestClient(make_app(service, user)).post(
            "/api/watchlists/research", json={"tickers": ["AAPL", "MSFT"]}
        )

    assert response.status_code == 200
    assert service.calls == [("research", "auth0|alice", ["AAPL", "MSFT"])]
