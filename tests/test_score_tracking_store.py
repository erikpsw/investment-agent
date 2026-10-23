from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from investment.data.score_tracking_store import InMemoryScoreTrackingStore, TrackingConflict


def sample(stamp="2026-10-20T07:00:00+00:00", score=70):
    return {"market": "US", "ticker": "AAPL", "mode": "balanced", "formula_version": "v2",
        "config_fingerprint": "a", "quote_as_of": stamp, "formula_score": score}


def test_snapshot_idempotence_order_and_user_isolation():
    store = InMemoryScoreTrackingStore()
    first = store.append_snapshot("alice", sample())
    assert store.append_snapshot("alice", sample())["snapshot"]["id"] == first["snapshot"]["id"]
    store.append_snapshot("alice", sample("2026-10-21T07:00:00+00:00", 75))
    older = store.append_snapshot("alice", sample("2026-10-19T07:00:00+00:00", 65))
    assert older["snapshot"]["formula_score"] == 75
    assert len(store.history("alice", "US", "AAPL")["items"]) == 2
    assert store.history("bob", "US", "AAPL")["items"] == []


def test_same_quote_with_conflicting_inputs_is_rejected():
    store = InMemoryScoreTrackingStore()
    store.append_snapshot("alice", sample())
    with pytest.raises(TrackingConflict):
        store.append_snapshot("alice", sample(score=90))


def test_history_copies_and_stable_pagination():
    store = InMemoryScoreTrackingStore()
    store.append_snapshot("alice", sample())
    store.append_snapshot("alice", sample("2026-10-21T07:00:00+00:00", 75))
    page = store.history("alice", "US", "AAPL", limit=1)
    page["items"][0]["formula_score"] = 0
    assert store.history("alice", "US", "AAPL")["items"][0]["formula_score"] == 75
    assert store.history("alice", "US", "AAPL", cursor=page["next_cursor"], limit=1)["items"][0]["formula_score"] == 70


def test_postgrest_business_conflict_is_mapped_without_retry():
    from unittest.mock import Mock
    from investment.data.score_tracking_store import SupabaseScoreTrackingStore
    class ConflictError(Exception): code="PT409"
    client=Mock()
    client.rpc.return_value.execute.side_effect=ConflictError("revision conflict")
    with pytest.raises(TrackingConflict):
        SupabaseScoreTrackingStore(client).apply_event("alice",str(uuid4()),0,{"action":"set_cash","currency":"USD","amount":1})
    assert client.rpc.return_value.execute.call_count==1
