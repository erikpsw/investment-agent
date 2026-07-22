import importlib.util
from pathlib import Path
from unittest.mock import Mock

import requests


def load_module():
    path = Path(__file__).resolve().parents[1] / "data" / "sector_scanner.py"
    spec = importlib.util.spec_from_file_location("sector_scanner_for_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sector_history_retries_an_alternate_endpoint(monkeypatch):
    module = load_module()
    calls = []

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "data": {
            "name": "测试板块",
            "klines": [
                "2026-07-20,1,10,11,9,100,1000,2,1,0,3",
                "2026-07-21,1,11,12,10,120,1200,2,10,0,4",
            ],
        }
    }

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise requests.Timeout("primary timed out")
        return response

    monkeypatch.setattr(module.requests, "get", fake_get)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    result = module.sector_history("BK1326", days=30)

    assert len(calls) == 2
    assert calls[0] != calls[1]
    assert result["name"] == "测试板块"
    assert len(result["bars"]) == 2
