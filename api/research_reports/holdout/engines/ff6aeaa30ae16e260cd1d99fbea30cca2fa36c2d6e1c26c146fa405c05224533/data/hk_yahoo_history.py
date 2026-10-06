"""Independent HK research archives with matching raw and adjusted Yahoo prices."""
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
from investment.data.foreign_formula import _validated_bars
from investment.data.formula_scoring import number


def hk_archive_folder(history_root: Path, universe: str) -> Path:
    """Keep catalog downloads from changing the frozen snapshot experiment."""
    if universe not in ("snapshot", "catalog"):
        raise ValueError("Unknown archive universe")
    folder = history_root / "yahoo-hk"
    return folder / "catalog" if universe == "catalog" else folder


def parse_hk_history(payload: dict, ticker: str, first: str, last: str) -> list[dict]:
    symbol = f"{ticker[2:].lstrip('0').zfill(4)}.HK"
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    if meta.get("symbol") != symbol or meta.get("currency") != "HKD" or meta.get("instrumentType") != "EQUITY":
        raise ValueError("Historical symbol, currency or instrument type mismatch")
    stamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    adjusted = result["indicators"]["adjclose"][0]["adjclose"]
    if any(len(quote[key]) != len(stamps) for key in ("open", "high", "low", "close", "volume")) or len(adjusted) != len(stamps):
        raise ValueError("Historical arrays are not aligned")
    bars = []
    for i, stamp in enumerate(stamps):
        day = datetime.fromtimestamp(stamp, ZoneInfo("Asia/Hong_Kong")).date().isoformat()
        if not first <= day <= last:
            continue
        close, adj = number(quote["close"][i]), number(adjusted[i])
        if close is None or adj is None or close <= 0 or adj <= 0:
            raise ValueError("Missing raw or adjusted closing price")
        factor = adj / close
        bar = {"date": day, "raw_close": close, "share_scale": 1 / factor, "history_source": "Yahoo", "price_basis": "adjusted", "volume": number(quote["volume"][i])}
        for key in ("open", "high", "low", "close"):
            value = number(quote[key][i])
            bar[key] = value * factor if value is not None else None
        bars.append(bar)
    return _validated_bars(bars, last)


def load_hk_archive(folder: Path, ticker: str) -> dict:
    audit = json.loads((folder / "download-audit.json").read_text(encoding="utf-8"))
    record = next((row for row in audit["records"] if row["ticker"] == ticker), {})
    if record.get("status") != "ok":
        raise ValueError("Latest download did not validate this security")
    saved = json.loads((folder / f"{ticker}.json").read_text(encoding="utf-8"))
    raw = (folder / f"{ticker}-response.json").read_bytes()
    if saved.get("manifest_sha256") != audit["manifest_sha256"] or hashlib.sha256(raw).hexdigest() != record.get("response_sha256") or saved.get("response_sha256") != record.get("response_sha256"):
        raise ValueError("Archive provenance mismatch")
    bounds = saved["requested_range"]
    bars = parse_hk_history(json.loads(raw), ticker, bounds["first"], bounds["last"])
    if bars != saved["bars"]:
        raise ValueError("Archived bars differ from validated response")
    return saved
