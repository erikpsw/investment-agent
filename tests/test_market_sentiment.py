"""Unit and route tests for the 3-market quantitative sentiment engine."""
from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

import api.index as vercel_api
import api.main as local_api
import investment.data.market_sentiment as ms


def _dates(n: int, start: date = date(2025, 1, 1)) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


@pytest.mark.parametrize(
    ("score", "expected_regime", "expected_range"),
    [
        (0.0, "extreme_fear", "75% - 90%"),
        (19.9, "extreme_fear", "75% - 90%"),
        (20.0, "fear", "60% - 75%"),
        (34.9, "fear", "60% - 75%"),
        (35.0, "neutral", "45% - 60%"),
        (64.9, "neutral", "45% - 60%"),
        (65.0, "greed", "30% - 45%"),
        (79.9, "greed", "30% - 45%"),
        (80.0, "extreme_greed", "15% - 30%"),
        (100.0, "extreme_greed", "15% - 30%"),
    ],
)
def test_classify_sentiment_regime_boundaries(score, expected_regime, expected_range):
    res = ms.classify_sentiment_regime(score)
    assert res["regime"] == expected_regime
    assert res["position_range"] == expected_range


@pytest.mark.parametrize(
    ("score", "trend_bull", "expected_range"),
    [
        (10.0, True, "95% - 100%"),
        (25.0, True, "90% - 100%"),
        (50.0, True, "80% - 90%"),
        (72.0, True, "75% - 85%"),
        (88.0, True, "60% - 75%"),
        (10.0, False, "75% - 90%"),
        (25.0, False, "55% - 70%"),
        (50.0, False, "40% - 55%"),
        (72.0, False, "30% - 45%"),
        (88.0, False, "20% - 35%"),
    ],
)
def test_classify_us_regime_position_bands(score, trend_bull, expected_range):
    res = ms.classify_sentiment_regime(score, market="US", trend_bull=trend_bull)
    assert res["position_range"] == expected_range


def test_hysteresis_regime_deadband_and_jumps():
    # Inside ±3 buffer around 35: stays in neutral
    assert ms.apply_hysteresis_regime(33.5, "neutral", buffer=3.0) == "neutral"
    # Drops past 35 - 3 = 32: switches to fear
    assert ms.apply_hysteresis_regime(31.5, "neutral", buffer=3.0) == "fear"
    # Inside buffer on way back up (<= 38): stays in fear
    assert ms.apply_hysteresis_regime(37.0, "fear", buffer=3.0) == "fear"
    # Rises past 38: returns to neutral
    assert ms.apply_hysteresis_regime(38.5, "fear", buffer=3.0) == "neutral"
    # Multi-tier jump from neutral to extreme_fear
    assert ms.apply_hysteresis_regime(15.0, "neutral", buffer=3.0) == "extreme_fear"


def test_detect_right_turn_confirmation():
    # Recent fear trough (18) rebounding to 28 + vol cooling + price reclaiming MA10
    scores = [45, 40, 32, 24, 18, 20, 23, 28]
    closes = [100, 98, 95, 92, 90, 91, 93, 96, 97, 99]
    vols = [20, 22, 25, 30, 34, 32, 29, 27, 25, 22]
    rt = ms.detect_right_turn(scores, closes, vols)
    assert rt["confirmed"] is True
    assert len(rt["confirmations"]) >= 2

    # No recent fear trough -> must NOT confirm right turn
    calm_scores = [55, 52, 50, 48, 49, 53, 56, 60]
    assert ms.detect_right_turn(calm_scores, closes, vols)["confirmed"] is False


def test_resonance_requires_score_confirmation():
    watch = ms._evaluate_resonance(42.0, ["trigger A", "trigger B"], [])
    assert watch["signal"] == "watch_bottom"
    confirmed = ms._evaluate_resonance(30.0, ["trigger A", "trigger B"], [])
    assert confirmed["signal"] == "bottom"
    extreme = ms._evaluate_resonance(18.0, ["trigger A"], [])
    assert extreme["signal"] == "bottom"
    watch_top = ms._evaluate_resonance(62.0, [], ["top A", "top B"])
    assert watch_top["signal"] == "watch_top"
    confirmed_top = ms._evaluate_resonance(70.0, [], ["top A", "top B"])
    assert confirmed_top["signal"] == "top"


def test_cn_extreme_bottom_and_top_resonance():
    days = _dates(260)
    # Falling index into oversold + shrinking turnover + high ERP + high QVIX + weak breadth
    closes = [4200.0 - i * 2.5 for i in range(260)]
    amounts = {d: 1.5e12 - i * 4.5e9 for i, d in enumerate(days)}
    qvix = [{"date": d, "close": 15.0 + (i / 260.0) * 18.0} for i, d in enumerate(days)]
    bottom = ms.score_cn_market({
        "hs300_bars": [{"date": d, "close": c} for d, c in zip(days, closes)],
        "sh_sz_amounts": amounts,
        "hs300_pe": 10.5,
        "hs300_dividend_yield": 3.8,
        "cn10y_yield": 1.6,
        "qvix_bars": qvix,
        "advance_ratio": 18.0,
        "up_count": 900,
        "down_count": 4100,
        "pb_below1_pct": 14.0,
    })
    assert bottom["score"] < 20.0
    assert bottom["regime"] == "extreme_fear"
    assert bottom["position_range"] == "75% - 90%"
    assert bottom["resonance"]["signal"] == "bottom"
    assert bottom["resonance"]["trigger_count"] >= 4
    assert len(bottom["history"]) == 60

    # Overheated bull market
    hot_closes = [3200.0 + i * 6.5 for i in range(260)]
    hot_amounts = {d: 7e11 + i * 7e9 for i, d in enumerate(days)}
    hot_qvix = [{"date": d, "close": 24.0 - (i / 260.0) * 12.0} for i, d in enumerate(days)]
    top = ms.score_cn_market({
        "hs300_bars": [{"date": d, "close": c} for d, c in zip(days, hot_closes)],
        "sh_sz_amounts": hot_amounts,
        "hs300_pe": 22.0,
        "cn10y_yield": 2.2,
        "qvix_bars": hot_qvix,
        "advance_ratio": 86.0,
        "pb_below1_pct": 2.0,
    })
    assert top["score"] >= 75.0
    assert top["regime"] in ("greed", "extreme_greed")
    assert top["position_range"] in ("30% - 45%", "15% - 30%")
    assert top["resonance"]["signal"] == "top"
    assert top["resonance"]["trigger_count"] >= 3
    vol_factor = next(f for f in top["factors"] if f["key"] == "volatility")
    assert vol_factor["score"] >= 45.0


def test_cn_directional_qvix_does_not_treat_bull_surge_as_panic():
    days = _dates(160)
    closes = [3200.0 + i * 5.0 for i in range(160)]
    amounts = {d: 1.5e12 for d in days}
    # High QVIX during strong uptrend above MA20 and MA120
    qvix = [{"date": d, "close": 14.0 + (i / 160.0) * 16.0} for i, d in enumerate(days)]
    res = ms.score_cn_market({
        "hs300_bars": [{"date": d, "close": c} for d, c in zip(days, closes)],
        "sh_sz_amounts": amounts,
        "hs300_pe": 14.0,
        "cn10y_yield": 1.8,
        "qvix_bars": qvix,
    })
    vol_factor = next(f for f in res["factors"] if f["key"] == "volatility")
    assert vol_factor["score"] >= 60.0
    assert not any("波动率" in t for t in res["resonance"]["triggers"])


def test_cn_graceful_degradation_without_qvix_or_pe():
    days = _dates(160)
    closes = [3900.0 + (i % 7) * 8.0 for i in range(160)]
    amounts = {d: 1.2e12 for d in days}
    res = ms.score_cn_market({
        "hs300_bars": [{"date": d, "close": c} for d, c in zip(days, closes)],
        "sh_sz_amounts": amounts,
        "hs300_pe": None,
        "cn10y_yield": None,
        "qvix_bars": [],
    })
    keys = {f["key"] for f in res["factors"]}
    assert "volatility" in keys
    assert "erp" not in keys
    assert 0.0 <= res["score"] <= 100.0


def test_hk_bottom_and_top_scoring():
    days = _dates(260)
    hsi_down = [{"date": d, "close": 24000.0 - i * 25.0, "amount": 9e10} for i, d in enumerate(days)]
    vhsi_high = [{"date": d, "close": 18.0 + (i / 260.0) * 18.0} for i, d in enumerate(days)]
    ah_high = [{"date": d, "close": 128.0 + (i / 260.0) * 20.0} for i, d in enumerate(days)]
    sb_inflow = [{"date": d, "net_yi": 25.0} for d in days[-25:]]

    bottom = ms.score_hk_market({
        "hsi_bars": hsi_down,
        "vhsi_bars": vhsi_high,
        "hsahp_bars": ah_high,
        "southbound_bars": sb_inflow,
    })
    assert bottom["score"] < 25.0
    assert bottom["resonance"]["signal"] == "bottom"
    assert bottom["resonance"]["trigger_count"] >= 3

    hsi_up = [{"date": d, "close": 17000.0 + i * 35.0, "amount": 1e11 + i * 1e9} for i, d in enumerate(days)]
    vhsi_low = [{"date": d, "close": 28.0 - (i / 260.0) * 14.0} for i, d in enumerate(days)]
    ah_low = [{"date": d, "close": 145.0 - (i / 260.0) * 26.0} for i, d in enumerate(days)]
    top = ms.score_hk_market({
        "hsi_bars": hsi_up,
        "vhsi_bars": vhsi_low,
        "hsahp_bars": ah_low,
        "southbound_bars": [{"date": d, "net_yi": -12.0} for d in days[-20:]],
    })
    assert top["score"] >= 75.0
    assert top["resonance"]["signal"] == "top"
    liq_factor = next(f for f in top["factors"] if f["key"] == "turnover")
    assert liq_factor["score"] <= 35.0


def test_us_scoring_and_cnn_fallback():
    days = _dates(160)
    spx_down = [{"date": d, "close": 6500.0 - i * 8.0} for i, d in enumerate(days)]
    vix_up = [{"date": d, "close": 16.0 + (i / 160.0) * 18.0} for i, d in enumerate(days)]
    vix3m = [{"date": d, "close": 24.0} for d in days]
    hyg = [{"date": d, "close": 80.0 - i * 0.04} for i, d in enumerate(days)]
    ief = [{"date": d, "close": 90.0 + i * 0.02} for i, d in enumerate(days)]

    bottom = ms.score_us_market({
        "cnn": {
            "fear_and_greed": {"score": 14.0, "rating": "extreme fear", "timestamp": "2026-11-27T23:59:59+00:00"},
            "market_volatility_vix": {"score": 12.0, "rating": "extreme fear", "data": [{"x": 1700000000000, "y": 34.0}]},
        },
        "spx_bars": spx_down,
        "vix_bars": vix_up,
        "vix3m_bars": vix3m,
        "hyg_bars": hyg,
        "ief_bars": ief,
    })
    assert bottom["score"] < 20.0
    assert bottom["resonance"]["signal"] == "bottom"
    assert bottom["position_range"] == "95% - 100%"
    assert len(bottom["sub_metrics"]) == 1

    # Fallback when CNN endpoint is empty
    no_cnn = ms.score_us_market({
        "cnn": {},
        "spx_bars": spx_down,
        "vix_bars": vix_up,
        "vix3m_bars": vix3m,
        "hyg_bars": hyg,
        "ief_bars": ief,
    })
    assert all(f["key"] != "cnn_fear_greed" for f in no_cnn["factors"])
    assert len(no_cnn["history"]) == 60
    assert no_cnn["score"] < 25.0


def test_snapshot_fallback_when_all_live_fetchers_fail(tmp_path, monkeypatch):
    snap_file = tmp_path / "sentiment.json"
    sample = {
        "generated_at": "2026-11-27T15:00:00+08:00",
        "stale": False,
        "markets": [
            {"market": "CN", "name": "A 股", "score": 28.0, "factors": [{"key": "erp", "name": "ERP", "weight": 1.0, "score": 28.0, "value": "6.0%", "detail": "ok"}]},
        ],
    }
    snap_file.write_text(json.dumps(sample), encoding="utf-8")
    monkeypatch.setattr(ms, "SNAPSHOT_PATH", snap_file)
    monkeypatch.setattr(ms, "_fetch_cn_payload", lambda: (_ for _ in ()).throw(RuntimeError("network down")))
    monkeypatch.setattr(ms, "_fetch_hk_payload", lambda: (_ for _ in ()).throw(RuntimeError("network down")))
    monkeypatch.setattr(ms, "_fetch_us_payload", lambda: (_ for _ in ()).throw(RuntimeError("network down")))

    with ms._cache_lock:
        ms._cache["payload"] = None
        ms._cache["expires_at"] = 0.0

    res = ms.get_market_sentiment(force_refresh=True)
    assert res["stale"] is True
    assert res["markets"][0]["market"] == "CN"
    assert res["markets"][0]["stale"] is True


@pytest.mark.parametrize("app_obj", [vercel_api.app, local_api.app])
def test_sentiment_route_mounted_on_both_apps(app_obj, monkeypatch):
    fake_result = {
        "generated_at": "2026-11-28T13:57:00+08:00",
        "stale": False,
        "live_markets": 3,
        "markets": [
            {
                "market": "CN",
                "name": "A 股",
                "score": 38.2,
                "regime": "neutral",
                "label": "中性震荡",
                "position_min": 45,
                "position_max": 60,
                "position_range": "45% - 60%",
                "action": "维持均衡仓位",
                "resonance": {"signal": "none", "label": "暂无极端共振信号", "trigger_count": 0, "triggers": []},
                "factors": [],
                "sub_metrics": [],
                "history": [],
                "stale": False,
            }
        ],
    }
    monkeypatch.setattr("investment.api.routes.sentiment.get_market_sentiment", lambda refresh=False: fake_result)

    async def call_api():
        async with AsyncClient(transport=ASGITransport(app=app_obj), base_url="http://test") as client:
            return await client.get("/api/market/sentiment")

    resp = asyncio.run(call_api())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["result"]["markets"][0]["score"] == 38.2
