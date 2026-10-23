from unittest.mock import Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from investment.api.auth import AuthenticatedUser
from investment.api.routes import portfolio, score_tracking
from investment.data.score_tracking_store import TrackingConflict


def setup(monkeypatch):
    app=FastAPI()
    app.include_router(portfolio.router,prefix="/api")
    app.dependency_overrides[portfolio.get_portfolio_writer]=lambda:AuthenticatedUser("alice")
    store=Mock()
    store.apply_event.return_value={"revision":3,"positions":[]}
    monkeypatch.setattr(score_tracking,"store_dependency",lambda:store)
    return TestClient(app),store


def test_uuid_transaction_canonicalizes_and_binds_authenticated_owner(monkeypatch):
    client,store=setup(monkeypatch)
    body={"action":"buy","market":"CN","instrument_id":"600000","quantity":100,"price":10,
        "request_id":"00000000-0000-0000-0000-000000000001","expected_revision":2,"executed_at":"2026-10-20T10:00:00Z"}
    assert client.post("/api/portfolio/transactions",json=body).status_code==200
    args=store.apply_event.call_args.args
    assert args[0]=="alice" and args[2]==2
    assert args[3]["instrument_id"]=="sh600000"
    assert args[3]["executed_at"]=="2026-10-20T10:00:00Z"
    store.apply_event.side_effect=TrackingConflict("refresh")
    assert client.post("/api/portfolio/transactions",json=body).status_code==409


def test_transaction_requires_revision_and_aware_execution_time(monkeypatch):
    client,store=setup(monkeypatch)
    body={"action":"set_cash","currency":"USD","amount":1000,"request_id":"00000000-0000-0000-0000-000000000001"}
    assert client.post("/api/portfolio/transactions",json=body).status_code==422
    assert client.post("/api/portfolio/transactions",json={**body,"expected_revision":0,"executed_at":"2026-10-20T10:00:00"}).status_code==422
    store.apply_event.assert_not_called()
