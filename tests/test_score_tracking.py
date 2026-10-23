import pytest
from investment.data.score_tracking import compare_score_history


def record(score=70, stamp="2026-10-20T07:00:00+00:00", **kwargs):
    return {"market": "CN", "ticker": "sh600000", "formula_score": score,
            "formula_version": "formula-v2", "mode": "balanced", "config_fingerprint": "a",
            "quote_as_of": stamp, "data_coverage": 1, "contributions": {"趋势": score}, **kwargs}


def test_comparable_score_changes_and_contribution_reasons():
    result = compare_score_history(record(75, "2026-10-22T07:00:00+00:00"), [record()], record(65))
    assert result["previous_delta"] == 5
    assert result["entry_delta"] == 10
    assert result["reasons"][0]["delta"] == 5
    assert result["trend_5d"]["status"] == "insufficient_history"


@pytest.mark.parametrize("field,value", [("mode", "aggressive"), ("formula_version", "v3"),
    ("config_fingerprint", "b"), ("market", "US"), ("ticker", "AAPL")])
def test_incomparable_snapshots_never_make_a_delta(field, value):
    result = compare_score_history(record(75), [record(**{field: value})], record(**{field: value}))
    assert result["previous_delta"] is None
    assert result["entry_delta"] is None


def test_same_or_future_quote_does_not_become_previous_observation():
    result = compare_score_history(record(), [record(80), record(90, "2026-10-23T07:00:00+00:00")], None)
    assert result["previous_delta"] is None


def test_quality_change_is_explicit():
    result = compare_score_history(record(75, "2026-10-22T07:00:00+00:00", data_coverage=.7), [record()], None)
    assert result["quality_changed"] is True


def test_detection_partial_failure_and_duplicate_quote_do_not_invent_history():
    import asyncio
    from datetime import datetime, timezone
    from investment.data.score_tracking import ScoreTrackingService
    from investment.data.score_tracking_store import InMemoryScoreTrackingStore
    store=InMemoryScoreTrackingStore()
    stamp=datetime.now(timezone.utc).isoformat()
    async def scorer(market,ticker,mode):
        if ticker=="MSFT": raise ValueError("provider unavailable")
        return record(stamp=stamp,market=market,ticker=ticker,price=100)
    service=ScoreTrackingService(store,scorer)
    first=asyncio.run(service.detect("alice",[{"market":"US","ticker":"AAPL"},{"market":"US","ticker":"MSFT"}],"balanced","request"))
    assert [r["status"] for r in first["items"]]==["ok","unavailable"]
    second=asyncio.run(service.detect("alice",[{"market":"US","ticker":"AAPL"}],"balanced","retry"))
    assert second["items"][0]["inserted"] is False
    assert len(store.history("alice","US","AAPL")["items"])==1


def test_closed_market_rejects_older_weekday_and_accepts_last_close():
    from datetime import datetime, timezone
    from investment.data.score_tracking import quality_status
    now=datetime(2026,10,22,12,0,tzinfo=timezone.utc) # Thursday 20:00 China
    assert quality_status(record(stamp="2026-10-21T07:00:00Z"),now)=="stale_quote"
    assert quality_status(record(stamp="2026-10-22T07:00:00Z"),now)=="ok"
