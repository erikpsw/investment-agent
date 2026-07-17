from pathlib import Path


def test_cache_directory_uses_temp_storage_on_vercel(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("TMPDIR", str(tmp_path))

    from data.runtime_paths import cache_directory

    cache_path = cache_directory("financial_cache")

    assert cache_path == Path(tmp_path) / "investment-agent" / "financial_cache"
    assert cache_path.is_dir()

