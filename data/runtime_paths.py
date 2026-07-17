"""Writable runtime paths for local and serverless environments."""

import os
from pathlib import Path


def cache_directory(name: str) -> Path:
    if os.getenv("VERCEL"):
        root = Path(os.getenv("TMPDIR", "/tmp")) / "investment-agent"
    else:
        root = Path(__file__).resolve().parent.parent / "storage"

    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    return path

