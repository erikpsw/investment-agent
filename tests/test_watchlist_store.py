from __future__ import annotations

from investment.data.watchlist_store import (
    InMemoryWatchlistStore,
    SupabaseWatchlistStore,
)


def test_users_have_independent_watchlist_documents() -> None:
    store = InMemoryWatchlistStore()
    store.save("auth0|alice", [{"id": "a", "name": "Alice", "items": []}])
    store.save("auth0|bob", [{"id": "b", "name": "Bob", "items": []}])

    assert store.load("auth0|alice").groups[0]["id"] == "a"
    assert store.load("auth0|bob").groups[0]["id"] == "b"


def test_supabase_store_reads_and_upserts_one_document_per_user() -> None:
    class Response:
        data = [
            {
                "groups": [{"id": "core", "name": "Core", "items": []}],
                "updated_at": "2026-07-22T10:00:00+00:00",
            }
        ]

    class Query:
        def __init__(self) -> None:
            self.upsert_payload = None

        def select(self, value):
            assert value == "groups,updated_at"
            return self

        def eq(self, key, value):
            assert (key, value) == ("user_id", "auth0|alice")
            return self

        def limit(self, value):
            assert value == 1
            return self

        def upsert(self, payload, on_conflict):
            assert on_conflict == "user_id"
            self.upsert_payload = payload
            return self

        def execute(self):
            return Response()

    class Client:
        def __init__(self) -> None:
            self.query = Query()

        def table(self, name):
            assert name == "user_watchlists"
            return self.query

    client = Client()
    store = SupabaseWatchlistStore("https://example.supabase.co", "service-key", client)

    loaded = store.load("auth0|alice")
    saved = store.save("auth0|alice", loaded.groups)

    assert loaded.groups[0]["id"] == "core"
    assert saved.storage == "supabase"
    assert client.query.upsert_payload["user_id"] == "auth0|alice"
    assert client.query.upsert_payload["groups"] == loaded.groups
