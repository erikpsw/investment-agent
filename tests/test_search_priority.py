from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from investment.api.routes import search


def test_hk_exact_code_precedes_cn_partial_matches():
    app = FastAPI()
    app.include_router(search.router, prefix="/api")
    candidates = [
        {"code": "sz000700", "name": "模塑科技", "market": "CN"},
        {"code": "hk00700", "name": "腾讯控股", "market": "HK"},
    ]
    with patch.object(search, "_search_hk_direct_quote", return_value=[]), patch.object(
        search.fetcher, "search", return_value=candidates
    ):
        result = TestClient(app).get("/api/search?q=00700&limit=8")
    assert result.status_code == 200
    assert result.json()["results"][0]["code"] == "hk00700"


def test_known_us_code_does_not_wait_for_yfinance():
    app = FastAPI()
    app.include_router(search.router, prefix="/api")
    with patch.object(search.fetcher, "search", return_value=[
        {"code": "AAPL", "name": "Apple", "market": "US"}
    ]), patch.object(search, "_search_yfinance") as remote:
        result = TestClient(app).get("/api/search?q=AAPL")
    assert result.status_code == 200
    assert result.json()["results"][0]["code"] == "AAPL"
    remote.assert_not_called()
