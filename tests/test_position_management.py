import pytest
from investment.data.position_management import risk_overview, protection_candidate, position_signal


def test_planned_risk_uses_current_price_and_unknown_is_not_zero():
    positions = [{"market": "US", "ticker": "AAPL", "currency": "USD", "quantity": 100}]
    detections = {"US:AAPL": {"price": 100, "quality_status": "ok", "price_basis": "raw"}}
    result = risk_overview(positions, {"USD": 10000}, {"risk_budget_percent": 1,
        "position_cap_percent": 20, "total_risk_percent": 5}, {"USD": 7, "CNY": 1}, detections,
        {"US:AAPL": {"episode_id": "a", "protection": {"stop_loss": 95, "currency": "USD", "price_basis": "raw", "episode_id": "a", "reference_price": 100}}})
    assert result["items"][0]["planned_risk_native"] == 500
    assert result["items"][0]["additional_quantity"] == 0  # Existing position already over 20%.
    missing = risk_overview(positions, {"USD": 10000}, {}, {}, detections, {})
    assert missing["unknown_risk_count"] == 1
    assert missing["planned_risk_base"] is None


def test_protection_cannot_loosen_or_cross_scales():
    base = {"stop_loss": 95, "currency": "USD", "price_basis": "raw", "episode_id": "a", "reference_price": 100}
    candidate = protection_candidate(base, {**base, "stop_loss": 90}, "a", {"currency": "USD", "price_basis": "raw", "reference_price": 100})
    assert candidate["stop_loss"] == 95
    assert protection_candidate(base, {**base, "stop_loss": 96}, "b", {"currency": "USD", "price_basis": "raw", "reference_price": 100})["status"] == "incomparable"
    assert protection_candidate(base, {**base, "stop_loss": 96}, "a", {"currency": "USD", "price_basis": "adjusted"})["status"] == "incomparable"


def test_stop_has_priority_over_high_score():
    signal = position_signal({"formula_score": 95, "price": 90, "quality_status": "ok"}, {}, {}, {"stop_loss": 95})
    assert signal["status"] == "stop_triggered"


def test_scale_change_pauses_effective_risk_and_signals():
    result = risk_overview([{"market":"US","ticker":"AAPL","currency":"USD","quantity":100}],
        {"USD":10000}, {}, {"USD":7}, {"US:AAPL":{"price":25,"price_basis":"raw","quality_status":"ok"}},
        {"US:AAPL":{"episode_id":"a","protection":{"episode_id":"a","currency":"USD","price_basis":"raw","reference_price":100,"stop_loss":95}}})
    assert result["planned_risk_base"] is None
    assert result["items"][0]["additional_quantity"] is None
    assert result["items"][0]["signal"]["status"] == "data_pending"


def test_legacy_currency_mismatch_invalidates_account_valuation():
    result=risk_overview([{"market":"US","ticker":"AAPL","currency":"CNY","quantity":10}],{"CNY":1000},{},{"USD":7},{"US:AAPL":{"price":100,"quality_status":"ok"}},{})
    assert result["account_value_base"] is None
    assert result["items"][0]["current_weight_percent"] is None


@pytest.mark.parametrize("market,ticker,currency,expected",[("US","AAPL","USD",12),("CN","sh600000","CNY",0),("HK","hk00017","HKD",None)])
def test_existing_risk_cash_fees_and_lot_constraints(market,ticker,currency,expected):
    plan={"episode_id":"a","currency":currency,"price_basis":"raw","reference_price":100,"stop_loss":95}
    result=risk_overview([{"market":market,"ticker":ticker,"currency":currency,"quantity":10}],{currency:10000},
        {"total_risk_percent":5},{currency:1},{market+":"+ticker:{"price":100,"quality_status":"ok","price_basis":"raw"}},
        {market+":"+ticker:{"episode_id":"a","protection":plan}})
    assert result["items"][0]["additional_quantity"]==expected


def test_portfolio_total_risk_takes_priority_over_improving_scores():
    positions=[{"market":"US","ticker":t,"currency":"USD","quantity":100} for t in ("AAPL","MSFT","NVDA")]
    plan={"episode_id":"a","currency":"USD","price_basis":"raw","reference_price":100,"stop_loss":90}
    detections={"US:"+p["ticker"]:{"price":100,"price_basis":"raw","quality_status":"ok","change":{"previous_delta":5}} for p in positions}
    managed={"US:"+p["ticker"]:{"episode_id":"a","protection":plan} for p in positions}
    result=risk_overview(positions,{"USD":70000},{"total_risk_percent":2},{"USD":1},detections,managed)
    assert result["account_value_base"]==100000
    assert result["planned_risk_base"]==3000
    assert result["portfolio_over_risk"] is True
    assert all(row["signal"]["status"]=="over_budget" for row in result["items"])


def test_overview_settings_can_round_trip_through_settings_api():
    from investment.api.routes.score_tracking import RiskSettings
    result=risk_overview([],{}, {},{}, {},{})
    assert RiskSettings.model_validate(result["settings"]).mode=="balanced"
