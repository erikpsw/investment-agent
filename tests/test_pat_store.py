from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timedelta, timezone

from investment.data.pat_store import InMemoryPersonalAccessTokenStore


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class PersonalAccessTokenStoreTests(unittest.TestCase):
    def test_postgres_variable_fractional_timestamp_is_supported(self) -> None:
        from investment.data.pat_store import _parse_datetime
        parsed = _parse_datetime("2026-07-22T02:46:12.17274+00:00")
        self.assertEqual(parsed, datetime(2026, 7, 22, 2, 46, 12, 172740, tzinfo=timezone.utc))
        self.assertEqual(_parse_datetime("2026-07-22T02:46:12.1Z").microsecond, 100000)

    def setUp(self) -> None:
        self.clock = MutableClock(datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc))
        self.store = InMemoryPersonalAccessTokenStore(
            now=self.clock.now,
            secret_factory=lambda: "fixed-personal-access-secret",
        )

    def test_create_returns_secret_once_and_persists_only_its_hash(self) -> None:
        created = self.store.create("auth0|alice", "Codex MCP")

        self.assertEqual(created.token, "eai_pat_fixed-personal-access-secret")
        self.assertEqual(created.record.name, "Codex MCP")
        self.assertEqual(
            created.record.expires_at,
            self.clock.value + timedelta(days=90),
        )
        stored = self.store._records[created.record.id]
        self.assertNotIn("token", stored)
        self.assertNotIn(created.token, repr(stored))
        self.assertEqual(
            stored["token_hash"],
            hashlib.sha256(created.token.encode("utf-8")).hexdigest(),
        )

        listed = self.store.list_tokens("auth0|alice")
        self.assertEqual(listed, [created.record])
        self.assertFalse(hasattr(listed[0], "token"))

    def test_authenticate_updates_last_used_and_rejects_expired_token(self) -> None:
        created = self.store.create("auth0|alice", "Remote reader")

        identity = self.store.authenticate(created.token)

        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity.user_id, "auth0|alice")
        self.assertEqual(identity.scopes, ("portfolio:read",))
        self.assertEqual(
            self.store.list_tokens("auth0|alice")[0].last_used_at,
            self.clock.value,
        )

        self.clock.value = created.record.expires_at
        self.assertIsNone(self.store.authenticate(created.token))

    def test_revoke_is_owner_scoped_and_immediately_invalidates_token(self) -> None:
        created = self.store.create("auth0|alice", "MCP")

        self.assertFalse(self.store.revoke("auth0|bob", created.record.id))
        self.assertIsNotNone(self.store.authenticate(created.token))
        self.assertTrue(self.store.revoke("auth0|alice", created.record.id))
        self.assertIsNone(self.store.authenticate(created.token))
        self.assertEqual(
            self.store.list_tokens("auth0|alice")[0].revoked_at,
            self.clock.value,
        )

    def test_users_only_list_their_own_tokens(self) -> None:
        alice = self.store.create("auth0|alice", "Alice token")
        bob = self.store.create("auth0|bob", "Bob token")

        self.assertEqual(
            [record.id for record in self.store.list_tokens("auth0|alice")],
            [alice.record.id],
        )
        self.assertEqual(
            [record.id for record in self.store.list_tokens("auth0|bob")],
            [bob.record.id],
        )


if __name__ == "__main__":
    unittest.main()
