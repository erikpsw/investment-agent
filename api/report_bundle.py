"""Read curated deployment reports with local precedence and verified bundled bytes."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def bundle_folder(root):
    return Path(root) / "api/research_reports"


def _relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("Invalid report path")
    return path


def read_research_bytes(root, relative):
    relative = _relative(relative)
    local = Path(root) / "storage/stock_picker" / relative
    if local.exists():
        return local.read_bytes()
    for folder in (bundle_folder(root), Path(root) / "api/research_reports_joint_modes",
                   Path(root) / "api/research_reports_reviewed_hk", Path(root) / "api/research_reports_centered_risk",
                   Path(root) / "api/research_reports_risk_budget"):
        content = _read_bundle(folder, relative)
        if content is not None:
            return content
    return None


def _read_bundle(folder, relative):
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("Invalid report manifest")
    entry = manifest["files"].get(relative.as_posix())
    if entry is None:
        return None
    if not isinstance(entry, dict) or not isinstance(entry.get("sha256"), str) or not re.fullmatch("[a-f0-9]{64}", entry["sha256"]):
        raise ValueError("Invalid report manifest entry")
    blob = folder / _relative(entry["path"])
    if not blob.resolve().is_relative_to(folder.resolve()):
        raise ValueError("Report outside bundle")
    content = blob.read_bytes()
    if len(content) != entry["size"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
        raise ValueError("Bundled report integrity mismatch")
    return content
