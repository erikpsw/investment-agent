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
