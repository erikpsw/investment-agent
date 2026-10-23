from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
import pytest
from investment.api.auth import AuthenticatedUser
from investment.api.routes import score_tracking as routes
from investment.data.score_tracking_store import InMemoryScoreTrackingStore


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    app.dependency_overrides[routes.reader] = lambda: AuthenticatedUser("alice")
    app.dependency_overrides[routes.writer] = lambda: AuthenticatedUser("alice")
    app.dependency_overrides[routes.store_dependency] = lambda: InMemoryScoreTrackingStore()
    return TestClient(app)


def test_history_validates_range_and_market(client):
    assert client.get('/api/securities/US/AAPL/score-history?trading_days=90').json()['result']['items'] == []
    assert client.get('/api/securities/US/AAPL/score-history?trading_days=999').status_code == 422
    assert client.get('/api/securities/XX/AAPL/score-history').status_code == 422


def test_detection_rejects_nonmember_before_calling_scorer(client, monkeypatch):
    monkeypatch.setattr(routes, 'allowed_securities', lambda owner: {('US','AAPL')})
    response = client.post('/api/watchlists/detection',json={'securities':[{'market':'US','ticker':'MSFT'}],
        'mode':'balanced','request_id':'00000000-0000-0000-0000-000000000001'})
    assert response.status_code == 403


def test_batch_limit_and_numeric_validation(client):
    request = {'securities':[{'market':'US','ticker':'AAPL'}]*51,'request_id':'00000000-0000-0000-0000-000000000001'}
    assert client.post('/api/watchlists/detection',json=request).status_code == 422
    assert client.put('/api/portfolio/risk-settings',json={'total_risk_percent':999}).status_code == 422


def test_anonymous_cannot_read_history():
    app = FastAPI()
    app.include_router(routes.router, prefix='/api')
    assert TestClient(app).get('/api/securities/US/AAPL/score-history').status_code in (401,403)


def test_stale_protection_is_rejected_before_write(client, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    store = SimpleNamespace(get_state=Mock(return_value={"settings":{}}), latest=Mock(return_value={"US:AAPL":{
        "id":"00000000-0000-0000-0000-000000000001","quote_as_of":"2020-01-01T00:00:00Z","data_coverage":1,"market":"US","config_fingerprint":"a"}}), confirm_protection=Mock())
    client.app.dependency_overrides[routes.store_dependency] = lambda: store
    response=client.put('/api/portfolio/positions/US/AAPL/protection',json={"episode_id":"00000000-0000-0000-0000-000000000002","expected_revision":0,"plan":{
        "snapshot_id":"00000000-0000-0000-0000-000000000001","config_fingerprint":"a","quote_as_of":"2020-01-01T00:00:00Z","currency":"USD","reference_price":100,"stop_loss":95}})
    assert response.status_code == 409
    store.confirm_protection.assert_not_called()
