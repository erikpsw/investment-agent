import pytest
from fastapi import HTTPException
from investment.api.auth import AuthenticatedUser
from investment.api.action_trigger import trigger_updates


def test_trigger_requires_explicit_admin_even_when_logged_in(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS_ADMIN_SUBS', 'auth0|owner')
    with pytest.raises(HTTPException) as error:
        trigger_updates('US', AuthenticatedUser(sub='auth0|other'))
    assert error.value.status_code == 403


def test_trigger_is_unavailable_without_server_credential(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS_ADMIN_SUBS', 'auth0|owner')
    monkeypatch.delenv('GITHUB_ACTIONS_TOKEN', raising=False)
    with pytest.raises(HTTPException) as error:
        trigger_updates('US', AuthenticatedUser(sub='auth0|owner'))
    assert error.value.status_code == 503


def test_active_workflow_is_reused_without_dispatch(monkeypatch):
    from investment.api import action_trigger as module
    monkeypatch.setenv('GITHUB_ACTIONS_ADMIN_SUBS', 'auth0|owner')
    monkeypatch.setenv('GITHUB_ACTIONS_TOKEN', 'test-token')
    response = type('Response', (), {'raise_for_status': lambda self: None,
        'json': lambda self: {'workflow_runs': [{'status': 'queued', 'html_url': 'https://github.com/erikpsw/investment-agent/actions/runs/123'}]}})()
    monkeypatch.setattr(module.requests, 'get', lambda *a, **k: response)
    monkeypatch.setattr(module.requests, 'post', lambda *a, **k: pytest.fail('duplicate dispatch'))
    result = trigger_updates('US', AuthenticatedUser(sub='auth0|owner'))
    assert result['result']['runs'][0]['status'] == 'running'


def test_admin_can_only_dispatch_fixed_main_workflows(monkeypatch):
    from investment.api import action_trigger as module
    monkeypatch.setenv('GITHUB_ACTIONS_ADMIN_SUBS', 'auth0|owner')
    monkeypatch.setenv('GITHUB_ACTIONS_TOKEN', 'test-token')
    response = type('Response', (), {'raise_for_status': lambda self: None,
        'json': lambda self: {'workflow_runs': []}})()
    captured = []
    monkeypatch.setattr(module.requests, 'get', lambda *a, **k: response)
    monkeypatch.setattr(module.requests, 'post', lambda url, **kw: captured.append((url, kw['json'])) or response)
    result = trigger_updates('CN', AuthenticatedUser(sub='auth0|owner'))
    assert captured == [('https://api.github.com/repos/erikpsw/investment-agent/actions/workflows/cn-market-snapshot.yml/dispatches', {'ref': 'main'})]
    assert result['result']['runs'][0]['status'] == 'queued'


def test_pat_auth_cannot_dispatch_even_with_admin_subject(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS_ADMIN_SUBS', 'auth0|owner')
    with pytest.raises(HTTPException) as error:
        trigger_updates('US', AuthenticatedUser(sub='auth0|owner', auth_type='pat'))
    assert error.value.status_code == 403


def test_http_trigger_requires_bearer_authentication():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from investment.api.routes.formula_ranking import router
    app = FastAPI()
    app.include_router(router)
    assert TestClient(app).post('/formula-ranking/refresh?market=CN').status_code == 401
