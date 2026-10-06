"""Provenanced instrument classification for stock-only formula universes."""
from __future__ import annotations
import csv
import json
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"stock", "fund", "etf", "leveraged_etf", "warrant", "rights", "preferred", "unit", "debt", "unknown"}

@lru_cache(maxsize=1)
def catalog() -> dict:
    result = {}
    for filename, market in [("SSE", "CN"), ("SZSE", "CN"), ("HKEX", "HK"), ("NASDAQ", "US"), ("NYSE", "US")]:
        path = ROOT / "data/stock_lists" / f"{filename}.csv"
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                code = row["code"].strip()
                ticker = ("sh" if filename == "SSE" else "sz") + code.zfill(6) if market == "CN" else "hk" + code.zfill(5) if market == "HK" else code.upper()
                result[(market, ticker.upper())] = {"name": row.get("name", ""), "instrument_type": "etf" if row.get("type") in ("fund", "etf") else "stock", "classification_source": f"本地{filename}证券目录", "classification_as_of": None}
    path = ROOT / "storage/market/instrument-catalog.json"
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            for row in saved.get("rows", []):
                if row.get("instrument_type") in KINDS:
                    result[(row["market"], row["ticker"].upper())] = row
        except (ValueError, KeyError, OSError):
            pass  # Optional refresh must not break the bundled directory.
    return result

def name_kind(name: str) -> str | None:
    name = unicodedata.normalize("NFKC", name).upper()
    if re.search(r"\b(?:LEVERAGED|INVERSE|ULTRASHORT|ULTRAPRO)\b|^(?:FI|FL|XI|XL)[一二三123]|杠杆|槓桿|反向", name):
        return "leveraged_etf"
    if re.search(r"\bWARRANTS?\b|认股权证|認股權證|牛熊证|牛熊證", name):
        return "warrant"
    if re.search(r"\bRIGHTS?\b|供股权|供股權", name):
        return "rights"
    if re.search(r"\b(?:PREFERRED|PREFERENCE|PFD)\b|优先股|優先股", name):
        return "preferred"
    if re.search(r"\b(?:NOTES?|BONDS?|DEBENTURES?|ETN)\b|债券|債券", name):
        return "debt"
    if re.search(r"\bUNITS?\b", name):
        return "unit"
    if re.search(r"\bETF\b|EXCHANGE[ -]TRADED FUND|基金", name):
        return "etf"
    if re.search(r"\bFUND\b|\bINCOME TRUST\b|\bMUNICIPAL(?: INCOME)? TRUST\b|\bTERM TRUST\b", name):
        return "fund"
    return None

def classify_instrument(row: dict) -> dict:
    market = str(row.get("market") or "").upper()
    ticker = str(row.get("ticker") or "")
    known = catalog().get((market, ticker.upper()))
    inferred = name_kind(str(row.get("name") or "")) or name_kind(str((known or {}).get("name") or ""))
    declared = row.get("instrument_type")
    if inferred is not None:
        kind = inferred; source = "证券名称类型特征"; stamp = None
    elif declared in KINDS and declared != "unknown":
        kind = declared; source = row.get("classification_source") or "行情结构化证券类型"; stamp = row.get("classification_as_of")
    elif known:
        kind = known["instrument_type"]; source = known["classification_source"]; stamp = known.get("classification_as_of")
    else:
        kind = "unknown"; source = "未找到可验证证券类型"; stamp = None
    return {"instrument_type": kind, "classification_source": source, "classification_as_of": stamp}

def stock_candidates(rows: list[dict]) -> dict:
    accepted = []; excluded = []
    for row in rows:
        classification = classify_instrument(row)
        if classification["instrument_type"] == "stock":
            accepted.append({**row, **classification})
        else:
            excluded.append({"ticker": row.get("ticker"), **classification})
    return {"rows": accepted, "input_count": len(rows), "eligible_count": len(accepted), "excluded_count": len(excluded), "excluded_by_type": dict(Counter(row["instrument_type"] for row in excluded)), "excluded": excluded}
