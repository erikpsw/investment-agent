import json
import hashlib
import os
from datetime import datetime, timedelta
from typing import Any, Optional, Union
from pathlib import Path


class CacheManager:
    def __init__(self, cache_dir: Optional[Union[str, Path]] = None):
        if cache_dir is None:
            cache_dir = Path(__file__).parent.parent / "storage" / "cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hash_key}.json"

    def get(self, key: str, ttl_seconds: int = 300) -> Optional[Any]:
        path = self._get_cache_path(key)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                cache = json.load(f)

            cached_time = datetime.fromisoformat(cache.get("_cached_at", ""))
            if (datetime.now() - cached_time).total_seconds() > ttl_seconds:
                return None

            return cache.get("data")
        except Exception:
            return None

    def set(self, key: str, data: Any) -> None:
        path = self._get_cache_path(key)
        try:
            cache = {
                "_cached_at": datetime.now().isoformat(),
                "data": data
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def clear(self, key: str) -> None:
        path = self._get_cache_path(key)
        if path.exists():
            path.unlink()
