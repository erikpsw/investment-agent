"""Hash scoring inputs separately from raw prices and research engine sources."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def research_provenance(series: dict, settings: dict, source_files: dict[str, Path]) -> dict:
    sources = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in sorted(source_files.items())}
    return {
        "provenance_version": "scoring-inputs-v1",
        "scoring_input_fingerprint": _digest({"series": series, "settings": settings}),
        "research_settings": settings,
        "engine_fingerprint": _digest(sources),
        "engine_source_hashes": sources,
    }
