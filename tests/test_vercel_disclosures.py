"""Verify deployed routes in a clean serverless-like interpreter."""
import os
import subprocess
import sys


def test_lite_disclosures_do_not_require_document_downloader(tmp_path):
    environment = {**os.environ, "VERCEL": "1", "TMPDIR": str(tmp_path)}
    result = subprocess.run([sys.executable, "-c", """
import sys
sys.modules['sec_edgar_downloader'] = None
from unittest.mock import patch
from fastapi.testclient import TestClient
from investment.api.index import app
from investment.api.routes import foreign_reports, futures
from investment.data.runtime_paths import cache_directory
assert foreign_reports.sec_client.cache_dir == cache_directory('sec_filings')
assert foreign_reports.hkex_client.cache_dir == cache_directory('hkex_filings')
client = TestClient(app)
with patch.object(foreign_reports.sec_client, 'get_filings_list', return_value=[]):
    assert client.get('/api/foreign/us/filings/KLIC').status_code == 200
with patch.object(foreign_reports.hkex_client, 'get_announcements', return_value=[]):
    assert client.get('/api/foreign/hk/announcements/hk00700').status_code == 200
with patch.object(futures.client, 'search', return_value=[]):
    assert client.get('/api/futures/search?q=AU').status_code == 200
assert all(not route.path.startswith('/api/foreign/us/download') for route in app.routes)
"""], capture_output=True, text=True, env=environment, timeout=60)
    assert result.returncode == 0, result.stderr
